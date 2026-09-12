"""System-bus service entry point."""

from __future__ import annotations

import json
from pathlib import Path
from common.oh_no_parent_control_ui.diagnostic_events import (
    get_logger, error_code, operation_scope, log_version, configure_console, record_exception,
)
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from . import config
from .adapters import (
    ACCOUNTS_NAME, APP_FILTER_INTERFACE, PROPERTIES_INTERFACE,
    AccountsService, CallerCredentials, TimerUsage,
)
from .authorization import PolkitAuthorizer
from .app_termination import RunningAppTerminator
from .catalog import list_apps
from .core import Broker, BrokerError, Busy, InvalidRequest
from .extension_manager import ExtensionManager
from .execution_policy import FapolicydPolicy
from .logs import DailyLogWriter, configure_broker_logging
from .preferences import PreferenceStore

LOG = get_logger("service")
BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
CONFIG_PATH = os.environ.get("OH_NO_PARENT_CONTROL_CONFIG", "/etc/oh-no-parent-control/config.json")

INTROSPECTION_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="ListManagedUsers">
      <arg name="users" type="a(uss)" direction="out"/>
    </method>
    <method name="ListApprovers">
      <arg name="users" type="a(uss)" direction="out"/>
    </method>
    <method name="GetOwnAccount">
      <arg name="uid" type="u" direction="out"/>
      <arg name="label" type="s" direction="out"/>
      <arg name="icon_file" type="s" direction="out"/>
    </method>
    <method name="RequestAccess">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="approver_uid" type="u" direction="in"/>
      <arg name="duration_seconds" type="u" direction="in"/>
      <arg name="allow_soft_blocked_apps" type="b" direction="in"/>
      <arg name="correlation_id" type="s" direction="out"/>
      <arg name="result_code" type="s" direction="out"/>
    </method>
    <method name="RequestOwnAccess">
      <arg name="approver_uid" type="u" direction="in"/>
      <arg name="duration_seconds" type="u" direction="in"/>
      <arg name="allow_soft_blocked_apps" type="b" direction="in"/>
      <arg name="correlation_id" type="s" direction="out"/>
      <arg name="result_code" type="s" direction="out"/>
      <arg name="granted_duration_seconds" type="u" direction="out"/>
    </method>
    <method name="GetPreferences">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="preferences_json" type="s" direction="out"/>
    </method>
    <method name="ListApplications">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="applications" type="a(ssssasas)" direction="out"/>
    </method>
    <method name="GetTimeStatus">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="additional_one_time_grant_seconds" type="u" direction="in"/>
      <arg name="daily_allowance_remaining_seconds" type="u" direction="out"/>
      <arg name="one_time_grant_remaining_seconds" type="u" direction="out"/>
      <arg name="additional_grant_seconds" type="u" direction="out"/>
      <arg name="calculated_active_extension_seconds" type="u" direction="out"/>
    </method>
    <method name="CalculateRemainingTime">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="daily_allowance_remaining_seconds" type="u" direction="in"/>
      <arg name="one_time_grant_remaining_seconds" type="u" direction="in"/>
      <arg name="additional_one_time_grant_seconds" type="u" direction="in"/>
      <arg name="calculated_active_extension_seconds" type="u" direction="out"/>
    </method>
    <method name="CalculateOwnRemainingTime">
      <arg name="daily_allowance_remaining_seconds" type="u" direction="in"/>
      <arg name="calculated_active_extension_seconds" type="u" direction="out"/>
    </method>
    <method name="PrepareOwnSession">
      <arg name="reconciled" type="b" direction="out"/>
    </method>
    <method name="SetPreferences">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="preferences_json" type="s" direction="in"/>
      <arg name="saved_json" type="s" direction="out"/>
    </method>
    <method name="UpdateRequestPreferences">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="selected_duration" type="s" direction="in"/>
      <arg name="custom_minutes" type="d" direction="in"/>
      <arg name="allow_soft_blocked_apps" type="b" direction="in"/>
      <arg name="last_selected_approver_uid" type="u" direction="in"/>
      <arg name="saved_json" type="s" direction="out"/>
    </method>
    <method name="SetRequestMuted">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="surface" type="s" direction="in"/>
      <arg name="muted" type="b" direction="in"/>
      <arg name="saved_json" type="s" direction="out"/>
    </method>
    <method name="SetParentControl">
      <arg name="target_uid" type="u" direction="in"/>
      <arg name="enabled" type="b" direction="in"/>
      <arg name="daily_limit_minutes" type="u" direction="in"/>
      <arg name="saved_json" type="s" direction="out"/>
    </method>
    <method name="RevokeOneTimeGrant">
      <arg name="target_uid" type="u" direction="in"/>
    </method>
    <method name="ExportDiagnosticLogs">
      <arg name="archive" type="ay" direction="out"/>
    </method>
    <method name="GetStartupTimings">
      <arg name="timings" type="a{{st}}" direction="out"/>
    </method>
    <method name="LogEvent">
      <arg name="component" type="s" direction="in"/>
      <arg name="level" type="s" direction="in"/>
      <arg name="message" type="s" direction="in"/>
    </method>
  </interface>
</node>
"""


@dataclass(frozen=True)
class ServiceDependencies:
    """Injectable adapters used to compose the broker and D-Bus transport."""

    credentials: Any
    accounts: Any
    config_loader: Any
    authorizer: Any
    preferences: Any
    extensions: Any
    timer_usage: Any
    application_catalog: Any
    running_apps: Any
    monotonic: Any = time.monotonic
    now: Any = lambda: datetime.now().astimezone()
    broker_factory: Any = Broker
    policy_rescan_interval_seconds: float | None = 30


def production_dependencies(connection) -> ServiceDependencies:
    """Build the production dependency graph for one bus connection."""
    credentials = CallerCredentials(connection)
    preferences = PreferenceStore()
    accounts = AccountsService(connection, FapolicydPolicy(), preferences)
    return ServiceDependencies(
        credentials=credentials,
        accounts=accounts,
        config_loader=lambda: config.load(CONFIG_PATH),
        authorizer=PolkitAuthorizer(connection),
        preferences=preferences,
        extensions=ExtensionManager(),
        timer_usage=TimerUsage(connection),
        application_catalog=list_apps,
        running_apps=RunningAppTerminator(
            application_catalog=lambda uid: list_apps(accounts.get_user(uid)),
        ),
    )


class Service:
    def __init__(self, connection, log_writer, *, dependencies=None):
        # Real monotonic time, independent of injected policy/usage clocks.
        self._startup_times = {"started_ns": time.monotonic_ns()}
        self.connection = connection
        self._diagnostic_export_lock = threading.Lock()
        self._grant_observation_lock = threading.Lock()
        dependencies = dependencies or production_dependencies(connection)
        self.credentials = dependencies.credentials
        self.accounts = dependencies.accounts
        self.broker = dependencies.broker_factory(
            dependencies.config_loader,
            dependencies.authorizer,
            self.accounts,
            dependencies.preferences,
            dependencies.extensions,
            dependencies.timer_usage,
            application_catalog=dependencies.application_catalog,
            running_apps=dependencies.running_apps,
            monotonic=dependencies.monotonic,
            now=dependencies.now,
            caller_alive=self.credentials.alive,
        )
        # Rules persist across broker restarts, then are reconciled against
        # AccountsService before accepting calls so deleted or changed users
        # cannot inherit stale execution policy.
        self.accounts.sync_execution_policy()
        self._startup_times["policy_ready_ns"] = time.monotonic_ns()
        refreshed_uids = self.broker.refresh_enabled_extensions()
        self._startup_times["extensions_ready_ns"] = time.monotonic_ns()
        if refreshed_uids:
            LOG.info("service.001", child_count=len(refreshed_uids))
        try:
            cap_uids = self.broker.clear_live_session_runtime_caps()
        except Exception as error:
            LOG.error("service.002", error_type=error_code(error))
        else:
            if cap_uids:
                LOG.info("service.003", child_count=len(cap_uids))
        self._startup_times["caps_attempted_ns"] = time.monotonic_ns()
        self.node_info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
        self.log_writer = log_writer
        self._app_filter_signal_id = self.connection.signal_subscribe(
            ACCOUNTS_NAME, PROPERTIES_INTERFACE, "PropertiesChanged",
            None, APP_FILTER_INTERFACE, Gio.DBusSignalFlags.NONE,
            self._app_filter_changed,
        )
        # Directory guards are the security boundary; this bounded periodic
        # reconciliation only admits newly discovered safe nonmatches after
        # they have been classified.  A dropped filesystem notification can
        # therefore cause inconvenience, never a wildcard bypass.
        self._policy_rescan_stop = threading.Event()
        self._policy_rescan_interval_seconds = (
            dependencies.policy_rescan_interval_seconds
        )
        self._policy_rescan_thread = None
        if self._policy_rescan_interval_seconds is not None:
            self._policy_rescan_thread = threading.Thread(
                target=self._periodic_policy_rescan,
                name="broker-policy-rescan",
                daemon=True,
            )
            self._policy_rescan_thread.start()
        self._registration_id = None
        self._grant_signal_id = self.connection.signal_subscribe(
            ACCOUNTS_NAME, PROPERTIES_INTERFACE, "PropertiesChanged",
            None, "com.endlessm.ParentalControls.SessionLimits",
            Gio.DBusSignalFlags.NONE, self._grant_changed,
        )

    def _periodic_policy_rescan(self):
        while not self._policy_rescan_stop.wait(
                self._policy_rescan_interval_seconds):
            self._sync_execution_policy_after_signal()
            self._observe_grants()

    def _app_filter_changed(self, *_args):
        # Mirror supported AccountsService changes regardless of which broker
        # transaction or administrator operation initiated them.
        threading.Thread(
            target=self._sync_execution_policy_after_signal,
            daemon=True,
        ).start()

    def _observe_grants(self):
        try:
            self.broker.observe_grants()
        except Exception as error:
            LOG.warning("service.grant-observation-failed", error_type=error_code(error))

    def _grant_changed(self, *_args):
        # Coalesce signal bursts; diagnostics must not create an unbounded
        # number of workers or hold up the main D-Bus loop.
        if not self._grant_observation_lock.acquire(blocking=False):
            return
        try:
            threading.Thread(target=self._grant_observation_worker, daemon=True).start()
        except Exception:
            self._grant_observation_lock.release()

    def _grant_observation_worker(self):
        try:
            self._observe_grants()
        finally:
            self._grant_observation_lock.release()

    def _health_snapshot(self):
        result = {}
        for key, name in (("accounts", "org.freedesktop.Accounts"),
                          ("timer", "org.freedesktop.MalcontentTimer1"),
                          ("polkit", "org.freedesktop.PolicyKit1"),
                          ("systemd", "org.freedesktop.systemd1")):
            try:
                owned, = self.connection.call_sync(
                    "org.freedesktop.DBus", "/org/freedesktop/DBus",
                    "org.freedesktop.DBus", "NameHasOwner", GLib.Variant("(s)", (name,)),
                    GLib.VariantType.new("(b)"), Gio.DBusCallFlags.NONE, 1000, None,
                ).unpack()
                result[key] = "available" if owned else "inactive"
            except Exception:
                result[key] = "unknown"
        try:
            incomplete = Path("/var/lib/oh-no-parent-control/migration-in-progress").exists()
            result["migration"] = "incomplete" if incomplete else "available"
        except OSError:
            result["migration"] = "unknown"
        result["storage"] = self.log_writer.storage_state()
        for probe, status in result.items():
            get_logger("runtime").info("runtime.health", probe=probe, status=status)
        return result

    def _sync_execution_policy_after_signal(self):
        try:
            self.accounts.sync_execution_policy()
        except Exception:
            LOG.error("service.004")

    def register(self):
        if self._registration_id is not None:
            raise RuntimeError("D-Bus service is already registered")
        self._startup_times["register_started_ns"] = time.monotonic_ns()
        self._registration_id = self.connection.register_object_with_closures2(
            OBJECT_PATH, self.node_info.interfaces[0], self._method_call, None, None
        )
        if not self._registration_id:
            self._registration_id = None
            raise RuntimeError("D-Bus object registration failed")
        self._startup_times["register_finished_ns"] = time.monotonic_ns()
        start = self._startup_times["started_ns"]
        LOG.info("service.ready",
                 policy_ms=(self._startup_times["policy_ready_ns"] - start) // 1_000_000,
                 extensions_ms=(self._startup_times["extensions_ready_ns"] - start) // 1_000_000,
                 register_ms=(self._startup_times["register_finished_ns"] -
                              self._startup_times["register_started_ns"]) // 1_000_000,
                 total_ms=(self._startup_times["register_finished_ns"] - start) // 1_000_000)
        self._grant_changed()

    def close(self):
        """Release transport resources owned by this service instance."""
        self._policy_rescan_stop.set()
        if self._policy_rescan_thread is not None:
            self._policy_rescan_thread.join(timeout=1)
            self._policy_rescan_thread = None
        if self._grant_signal_id is not None:
            self.connection.signal_unsubscribe(self._grant_signal_id)
            self._grant_signal_id = None
        if self._app_filter_signal_id is not None:
            self.connection.signal_unsubscribe(self._app_filter_signal_id)
            self._app_filter_signal_id = None
        if self._registration_id is not None:
            self.connection.unregister_object(self._registration_id)
            self._registration_id = None

    @operation_scope
    def _method_call(self, _connection, sender, _path, _interface, method,
                     parameters, invocation):
        try:
            caller_uid = self.credentials.uid(sender)
            deferred_reply = False
            if method not in ("LogEvent", "CalculateOwnRemainingTime"):
                LOG.info("service.006", method=method)
            if method == "ListManagedUsers":
                users = self.broker.list_managed_users(caller_uid)
                invocation.return_value(GLib.Variant(
                    "(a(uss))",
                    ([(user.uid, user.label, user.icon_file) for user in users],),
                ))
            elif method == "ListApprovers":
                users = self.broker.list_approvers(caller_uid)
                invocation.return_value(GLib.Variant(
                    "(a(uss))",
                    ([(user.uid, user.label, user.icon_file) for user in users],),
                ))
            elif method == "GetOwnAccount":
                user = self.broker.get_own_account(caller_uid)
                invocation.return_value(GLib.Variant(
                    "(uss)", (user.uid, user.label, user.icon_file),
                ))
            elif method == "RequestAccess":
                target_uid, approver_uid, duration_seconds, allow_soft = parameters.unpack()
                deferred_reply = True
                threading.Thread(
                    target=self._request_worker,
                    args=(invocation, caller_uid, sender, target_uid,
                          approver_uid, duration_seconds, allow_soft),
                    daemon=True,
                ).start()
            elif method == "RequestOwnAccess":
                approver_uid, duration_seconds, allow_soft = parameters.unpack()
                deferred_reply = True
                threading.Thread(
                    target=self._request_own_worker,
                    args=(invocation, caller_uid, sender, approver_uid,
                          duration_seconds, allow_soft),
                    daemon=True,
                ).start()
            elif method == "GetPreferences":
                target_uid, = parameters.unpack()
                value = self.broker.get_preferences(caller_uid, target_uid)
                invocation.return_value(GLib.Variant("(s)", (json.dumps(value),)))
            elif method == "ListApplications":
                target_uid, = parameters.unpack()
                applications = self.broker.list_applications(caller_uid, target_uid)
                invocation.return_value(GLib.Variant("(a(ssssasas))", ([
                    (app["id"], app["name"], app["description"], app["icon"],
                     list(app["targets"]), list(app.get("suggested_patterns", ())))
                    for app in applications
                ],)))
            elif method == "GetTimeStatus":
                target_uid, additional = parameters.unpack()
                status = self.broker.get_time_status(
                    caller_uid, target_uid, additional,
                )
                invocation.return_value(GLib.Variant("(uuuu)", (
                    status.daily_allowance_remaining_seconds,
                    status.one_time_grant_remaining_seconds,
                    status.additional_one_time_grant_seconds,
                    status.calculated_active_extension_seconds,
                )))
            elif method == "CalculateRemainingTime":
                target_uid, daily, grant, additional = parameters.unpack()
                calculated = self.broker.calculate_remaining_time(
                    caller_uid, target_uid, daily, grant, additional,
                )
                invocation.return_value(GLib.Variant("(u)", (calculated,)))
            elif method == "CalculateOwnRemainingTime":
                daily, = parameters.unpack()
                calculated = self.broker.calculate_own_remaining_time(
                    caller_uid, daily,
                )
                invocation.return_value(GLib.Variant("(u)", (calculated,)))
            elif method == "PrepareOwnSession":
                deferred_reply = True
                threading.Thread(
                    target=self._prepare_own_session_worker,
                    args=(invocation, caller_uid),
                    daemon=True,
                ).start()
            elif method == "SetPreferences":
                target_uid, encoded = parameters.unpack()
                try:
                    value = json.loads(encoded)
                except json.JSONDecodeError as error:
                    raise InvalidRequest("preferences are not valid JSON") from error
                saved = self.broker.set_preferences(caller_uid, target_uid, value)
                invocation.return_value(GLib.Variant("(s)", (json.dumps(saved),)))
            elif method == "UpdateRequestPreferences":
                target_uid, selected, custom, allow_soft, approver_uid = parameters.unpack()
                saved = self.broker.update_request_preferences(
                    caller_uid, target_uid, selected, custom, allow_soft,
                    approver_uid,
                )
                invocation.return_value(GLib.Variant("(s)", (json.dumps(saved),)))
            elif method == "SetRequestMuted":
                target_uid, surface, muted = parameters.unpack()
                saved = self.broker.set_request_muted(
                    caller_uid, target_uid, surface, muted,
                )
                invocation.return_value(GLib.Variant("(s)", (json.dumps(saved),)))
            elif method == "SetParentControl":
                target_uid, enabled, daily_limit_minutes = parameters.unpack()
                saved = self.broker.set_parent_control(
                    caller_uid, target_uid, enabled, daily_limit_minutes,
                )
                invocation.return_value(GLib.Variant("(s)", (json.dumps(saved),)))
            elif method == "RevokeOneTimeGrant":
                target_uid, = parameters.unpack()
                self.broker.revoke_one_time_grant(caller_uid, target_uid)
                invocation.return_value(None)
            elif method == "ExportDiagnosticLogs":
                self.broker.authorize_diagnostic_export(caller_uid)
                if not self._diagnostic_export_lock.acquire(blocking=False):
                    raise Busy("a diagnostic export is already in progress")
                try:
                    threading.Thread(
                        target=self._export_logs_worker,
                        args=(invocation, caller_uid), daemon=True,
                    ).start()
                except Exception:
                    self._diagnostic_export_lock.release()
                    raise
                deferred_reply = True
            elif method == "GetStartupTimings":
                self.broker.authorize_diagnostic_export(caller_uid)
                invocation.return_value(GLib.Variant("(a{st})", (dict(self._startup_times),)))
            elif method == "LogEvent":
                component, level, message = parameters.unpack()
                self.broker.authorize_log_component(caller_uid, component)
                try:
                    self.log_writer.write(component, level, message, source_uid=caller_uid)
                except ValueError as error:
                    raise InvalidRequest(str(error)) from error
                invocation.return_value(None)
            else:
                LOG.warning("service.007", method=method)
                invocation.return_dbus_error(
                    f"{BUS_NAME}.Error.InvalidRequest", "unknown method"
                )
            if method not in ("LogEvent", "CalculateOwnRemainingTime") and not deferred_reply:
                LOG.info("service.008", method=method)
        except BrokerError as error:
            LOG.warning("service.009", method=method, error_type=error_code(error))
            invocation.return_dbus_error(error.dbus_name, str(error))
        except Exception as error:
            LOG.error("service.010", method=method, error_type=error_code(error))
            invocation.return_dbus_error(f"{BUS_NAME}.Error.Failed", "service failure")

    def _export_logs_worker(self, invocation, caller_uid):
        data = None
        try:
            data = self.log_writer.snapshot(health=self._health_snapshot())
        except Exception as error:
            LOG.warning("service.011", error_type=error_code(error))
        GLib.idle_add(self._export_logs_done, invocation, caller_uid, data)

    def _export_logs_done(self, invocation, caller_uid, data):
        try:
            # Recheck live roles before releasing the archive. Keep the lock
            # through delivery so queued replies cannot accumulate archives.
            self.broker.authorize_diagnostic_export(caller_uid)
            if data is None:
                invocation.return_dbus_error(
                    f"{BUS_NAME}.Error.BackendFailure", "diagnostic logs unavailable",
                )
            else:
                archive = GLib.Variant.new_from_bytes(
                    GLib.VariantType.new("ay"), GLib.Bytes.new(data), True,
                )
                invocation.return_value(GLib.Variant.new_tuple(archive))
                LOG.info("service.012", bytes=len(data))
        except BrokerError as error:
            invocation.return_dbus_error(error.dbus_name, str(error))
        finally:
            self._diagnostic_export_lock.release()
        return GLib.SOURCE_REMOVE

    @operation_scope
    def _request_worker(self, invocation, caller_uid, sender, target_uid,
                        approver_uid, duration_seconds, allow_soft):
        try:
            result = self.broker.request_access(
                caller_uid, sender, target_uid, approver_uid, duration_seconds, allow_soft
            )
            LOG.info("service.013")
            GLib.idle_add(self._return_value, invocation, result)
        except BrokerError as error:
            LOG.warning("service.014", error_type=error_code(error))
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception as error:
            LOG.error("service.015", error_type=error_code(error))
            GLib.idle_add(
                self._return_error, invocation, f"{BUS_NAME}.Error.Failed", "service failure"
            )

    @operation_scope
    def _request_own_worker(self, invocation, caller_uid, sender,
                            approver_uid, duration_seconds, allow_soft):
        try:
            result = self.broker.request_own_access(
                caller_uid, sender, approver_uid, duration_seconds, allow_soft,
            )
            LOG.info("service.016")
            GLib.idle_add(self._return_own_value, invocation, result)
        except BrokerError as error:
            LOG.warning("service.017", error_type=error_code(error))
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception as error:
            LOG.error("service.018", error_type=error_code(error))
            GLib.idle_add(
                self._return_error, invocation, f"{BUS_NAME}.Error.Failed", "service failure"
            )

    @operation_scope
    def _prepare_own_session_worker(self, invocation, caller_uid):
        try:
            reconciled = self.broker.prepare_own_session(caller_uid)
            LOG.info("service.019")
            GLib.idle_add(
                self._return_value_variant, invocation,
                GLib.Variant("(b)", (reconciled,)),
            )
        except BrokerError as error:
            LOG.warning("service.020", error_type=error_code(error))
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception as error:
            LOG.error("service.021", error_type=error_code(error))
            GLib.idle_add(
                self._return_error, invocation, f"{BUS_NAME}.Error.Failed", "service failure"
            )

    @staticmethod
    def _return_value(invocation, result):
        invocation.return_value(GLib.Variant("(ss)", result))
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _return_own_value(invocation, result):
        invocation.return_value(GLib.Variant("(ssu)", result))
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _return_value_variant(invocation, result):
        invocation.return_value(result)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _return_error(invocation, name, message):
        invocation.return_dbus_error(name, message)
        return GLib.SOURCE_REMOVE


def main():
    if os.geteuid() != 0:
        configure_console()
        LOG.critical("service.022")
        return 1
    log_writer = DailyLogWriter()
    configure_broker_logging(log_writer)
    log_version()
    LOG.info("service.023")
    loop = GLib.MainLoop()
    service_holder = []
    startup_failed = []

    def on_bus_acquired(_connection, _name):
        try:
            service = Service(_connection, log_writer)
            service.register()
            service_holder.append(service)
            LOG.info("service.024")
        except Exception as error:
            startup_failed.append(True)
            record_exception(error)
            LOG.error("service.025")
            loop.quit()

    def on_name_lost(_connection, _name):
        LOG.critical("service.026")
        loop.quit()

    owner_id = Gio.bus_own_name(
        Gio.BusType.SYSTEM, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
        on_bus_acquired, None, on_name_lost,
    )
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, loop.quit)
    try:
        loop.run()
    finally:
        LOG.info("service.027")
        if service_holder:
            service_holder[0].close()
        Gio.bus_unown_name(owner_id)
    return 1 if startup_failed else 0


if __name__ == "__main__":
    from common.oh_no_parent_control_ui.diagnostic_events import run_cli
    sys.exit(run_cli(main))
