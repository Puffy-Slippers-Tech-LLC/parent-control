"""System-bus service entry point."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from . import config
from .adapters import (
    ACCOUNTS_NAME, APP_FILTER_INTERFACE, PROPERTIES_INTERFACE,
    AccountsService, CallerCredentials, PolkitAuthorizer, TimerUsage,
)
from .app_termination import RunningAppTerminator
from .catalog import list_apps
from .core import Broker, BrokerError, InvalidRequest
from .extension_manager import ExtensionManager
from .execution_policy import FapolicydPolicy
from .logs import DailyLogWriter, configure_broker_logging
from .preferences import PreferenceStore

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
    <method name="LogEvent">
      <arg name="component" type="s" direction="in"/>
      <arg name="level" type="s" direction="in"/>
      <arg name="message" type="s" direction="in"/>
    </method>
  </interface>
</node>
"""


class Service:
    def __init__(self, connection, log_writer):
        self.connection = connection
        self.credentials = CallerCredentials(connection)
        preferences = PreferenceStore()
        self.accounts = AccountsService(connection, FapolicydPolicy(), preferences)
        # Rules persist across broker restarts, then are reconciled against
        # AccountsService before accepting calls so deleted or changed users
        # cannot inherit stale execution policy.
        self.accounts.sync_execution_policy()
        self.broker = Broker(
            lambda: config.load(CONFIG_PATH), PolkitAuthorizer(connection),
            self.accounts, preferences, ExtensionManager(),
            TimerUsage(connection),
            application_catalog=list_apps,
            running_apps=RunningAppTerminator(),
            caller_alive=self.credentials.alive,
        )
        refreshed_uids = self.broker.refresh_enabled_extensions()
        if refreshed_uids:
            logging.info(
                "refreshed child extension payloads child_count=%d",
                len(refreshed_uids),
            )
        try:
            cap_uids = self.broker.clear_live_session_runtime_caps()
        except Exception:
            logging.exception("could not clear managed session runtime caps")
        else:
            if cap_uids:
                logging.info(
                    "cleared systemd session runtime caps child_count=%d",
                    len(cap_uids),
                )
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
        threading.Thread(target=self._periodic_policy_rescan, daemon=True).start()

    def _periodic_policy_rescan(self):
        while not self._policy_rescan_stop.wait(30):
            self._sync_execution_policy_after_signal()

    def _app_filter_changed(self, *_args):
        # Mirror supported AccountsService changes regardless of which broker
        # transaction or administrator operation initiated them.
        threading.Thread(
            target=self._sync_execution_policy_after_signal,
            daemon=True,
        ).start()

    def _sync_execution_policy_after_signal(self):
        try:
            self.accounts.sync_execution_policy()
        except Exception:
            logging.exception("app execution policy signal sync failed")

    def register(self):
        self.connection.register_object(
            OBJECT_PATH, self.node_info.interfaces[0], self._method_call, None, None
        )

    def _method_call(self, _connection, sender, _path, _interface, method,
                     parameters, invocation):
        try:
            caller_uid = self.credentials.uid(sender)
            if method != "LogEvent":
                logging.info("dbus method=%s caller=[Authorized user] stage=dispatch", method)
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
                threading.Thread(
                    target=self._request_worker,
                    args=(invocation, caller_uid, sender, target_uid,
                          approver_uid, duration_seconds, allow_soft),
                    daemon=True,
                ).start()
            elif method == "RequestOwnAccess":
                approver_uid, duration_seconds, allow_soft = parameters.unpack()
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
            elif method == "LogEvent":
                component, level, message = parameters.unpack()
                self.broker.authorize_log_component(caller_uid, component)
                try:
                    self.log_writer.write(component, level, message, source_uid=caller_uid)
                except ValueError as error:
                    raise InvalidRequest(str(error)) from error
                invocation.return_value(None)
            else:
                invocation.return_dbus_error(
                    f"{BUS_NAME}.Error.InvalidRequest", "unknown method"
                )
            if method != "LogEvent":
                logging.info("dbus method=%s caller=[Authorized user] outcome=accepted", method)
        except BrokerError as error:
            logging.warning("dbus method=%s outcome=denied error_type=%s",
                            method, type(error).__name__)
            invocation.return_dbus_error(error.dbus_name, str(error))
        except Exception as error:
            logging.error("dbus method=%s outcome=failed error_type=%s", method, type(error).__name__)
            invocation.return_dbus_error(f"{BUS_NAME}.Error.Failed", "service failure")

    def _request_worker(self, invocation, caller_uid, sender, target_uid,
                        approver_uid, duration_seconds, allow_soft):
        try:
            result = self.broker.request_access(
                caller_uid, sender, target_uid, approver_uid, duration_seconds, allow_soft
            )
            GLib.idle_add(self._return_value, invocation, result)
        except BrokerError as error:
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception as error:
            logging.error("request worker kind=kiosk outcome=failed error_type=%s", type(error).__name__)
            GLib.idle_add(
                self._return_error, invocation, f"{BUS_NAME}.Error.Failed", "service failure"
            )

    def _request_own_worker(self, invocation, caller_uid, sender,
                            approver_uid, duration_seconds, allow_soft):
        try:
            result = self.broker.request_own_access(
                caller_uid, sender, approver_uid, duration_seconds, allow_soft,
            )
            GLib.idle_add(self._return_own_value, invocation, result)
        except BrokerError as error:
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception as error:
            logging.error("request worker kind=child outcome=failed error_type=%s", type(error).__name__)
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
    def _return_error(invocation, name, message):
        invocation.return_dbus_error(name, message)
        return GLib.SOURCE_REMOVE


def main():
    if os.geteuid() != 0:
        logging.basicConfig(level=logging.INFO)
        logging.critical("broker must run as root")
        return 1
    log_writer = DailyLogWriter()
    configure_broker_logging(log_writer)
    logging.info("broker starting config=%s", CONFIG_PATH)
    loop = GLib.MainLoop()
    service_holder = []
    startup_failed = []

    def on_bus_acquired(_connection, _name):
        try:
            service = Service(_connection, log_writer)
            service.register()
            service_holder.append(service)
            logging.info("system bus acquired; broker ready")
        except Exception:
            startup_failed.append(True)
            logging.exception("broker initialization failed")
            loop.quit()

    def on_name_lost(_connection, _name):
        logging.critical("could not own the system-bus name")
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
        logging.info("broker stopping")
        Gio.bus_unown_name(owner_id)
    return 1 if startup_failed else 0


if __name__ == "__main__":
    sys.exit(main())
