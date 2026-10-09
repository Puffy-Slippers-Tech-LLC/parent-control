"""Policy and transactional behavior independent of D-Bus bindings."""

from __future__ import annotations

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code, record_exception
from common.oh_no_parent_control_ui.app_policy import replacement_policy_ids
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.localization import load_translations
from common.oh_no_parent_control_ui.languages import desktop_language_candidates
import gettext
from .grant_diagnostics import GrantDiagnostics
from .execution_policy import ExecutionPolicyError
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .config import Configuration, ConfigurationError, UINT32_MAX
from .whats_new import WhatsNewCatalog, WhatsNewError
from .preferences import (
    MAX_DAILY_LIMIT_MINUTES, MIN_DAILY_LIMIT_MINUTES, PreferencesError,
    blocked_patterns, blocked_targets, validate_preferences, validate_language, validate_notifications,
    validate_time_grant_presets, MIN_TIME_GRANT_SECONDS, MAX_TIME_GRANT_SECONDS,
)

LOG = get_logger("core")
_NO_ACKNOWLEDGEMENT = object()
MAX_LOCAL_MIDNIGHT_SECONDS = 26 * 60 * 60
MIN_REQUEST_SECONDS = MIN_TIME_GRANT_SECONDS
MAX_REQUEST_SECONDS = MAX_TIME_GRANT_SECONDS
MIN_MANAGED_UID = 1000
DAILY_LIMIT_FLAG = 1 << 1
APPROVER_USERNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*[$]?$")


class BrokerError(RuntimeError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.Failed"


class InvalidRequest(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.InvalidRequest"


class AccessDenied(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.AccessDenied"


class Busy(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.Busy"


class RateLimited(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.RateLimited"


class BackendFailure(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.BackendFailure"


class RollbackFailure(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.RollbackFailure"


@dataclass(frozen=True)
class UserAccount:
    uid: int
    username: str
    label: str
    is_admin: bool
    is_system: bool
    is_local: bool
    is_locked: bool = False
    icon_file: str = ""
    is_interactive: bool = True
    desktop_language: str = ""


@dataclass(frozen=True)
class TimeStatus:
    daily_allowance_remaining_seconds: int
    one_time_grant_remaining_seconds: int
    additional_one_time_grant_seconds: int
    calculated_active_extension_seconds: int


class Authorizer(Protocol):
    def check(self, request_kind: str, sender: str, correlation_id: str, target_label: str,
              approver_username: str, message: str) -> str: ...


class Accounts(Protocol):
    def list_users(self) -> tuple[UserAccount, ...]: ...
    def get_user(self, uid: int) -> UserAccount: ...
    def get_filter(self, target_uid: int) -> tuple[bool, tuple[str, ...]]: ...
    def validate_filter(self, target_uid: int, value: tuple[bool, tuple[str, ...]]) -> None: ...
    def set_filter(self, target_uid: int, value: tuple[bool, tuple[str, ...]]) -> None: ...
    def get_extension(self, target_uid: int) -> tuple[int, int]: ...
    def set_extension(self, target_uid: int, value: tuple[int, int]) -> None: ...
    def get_limit_type(self, target_uid: int) -> int: ...
    def set_limit_type(self, target_uid: int, value: int) -> None: ...
    def get_daily_limit(self, target_uid: int) -> int: ...
    def set_daily_limit(self, target_uid: int, value: int) -> None: ...


class Preferences(Protocol):
    def load(self, uid: int) -> dict: ...
    def save(self, uid: int, preferences: object) -> dict: ...
    def update_request(self, uid: int, selected: str, custom: float,
                       allow_soft: bool, last_selected_approver_uid: int = 0,
                       custom_unit: str = "minutes") -> dict: ...
    def update_request_muted(self, uid: int, surface: str, muted: bool) -> dict: ...
    def update_language(self, uid: int, language: object) -> str: ...
    def acknowledge_whats_new(self, uid: int, record_id: str, retained: set[str]) -> list[str]: ...


class Extensions(Protocol):
    def set_enabled(self, uid: int, enabled: bool, *,
                    recover_global_switch: bool = False) -> None: ...


class TimerUsage(Protocol):
    def query_usage(self, uid: int) -> tuple[tuple[int, int], ...]: ...
    def query_usage_as(
            self, uid: int, approver: UserAccount) -> tuple[tuple[int, int], ...]: ...


class RunningApps(Protocol):
    def has_running(self, target_uid: int, targets: tuple[str, ...],
                    patterns: tuple[str, ...]) -> bool: ...
    def preflight(self, target_uid: int, targets: tuple[str, ...],
                  patterns: tuple[str, ...]) -> None: ...
    def terminate(self, target_uid: int, targets: tuple[str, ...],
                  patterns: tuple[str, ...]) -> int: ...


def calculate_active_extension_seconds(
        daily_allowance_remaining_seconds: int,
        one_time_grant_remaining_seconds: int,
        additional_one_time_grant_seconds: int) -> int:
    values = (
        daily_allowance_remaining_seconds,
        one_time_grant_remaining_seconds,
        additional_one_time_grant_seconds,
    )
    if any(type(value) is not int or not 0 <= value <= UINT32_MAX
           for value in values):
        raise InvalidRequest("remaining-time values must be unsigned 32-bit integers")
    calculated = max(values[0], values[1]) + values[2]
    if calculated > UINT32_MAX:
        raise InvalidRequest("calculated ActiveExtension is too large")
    return calculated


def seconds_until_local_midnight(now: datetime) -> int:
    if now.tzinfo is None:
        raise ValueError("approval time must be timezone-aware")
    tomorrow = now.date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)
    seconds = int(midnight.timestamp() - now.timestamp())
    if not 0 < seconds <= MAX_LOCAL_MIDNIGHT_SECONDS:
        raise BackendFailure("local-midnight duration is outside the safe range")
    return seconds


def format_requested_duration(duration_seconds: int, translations=None) -> str:
    """Render validated request seconds using the child's private context."""
    if translations is None:
        translations = gettext.NullTranslations()
    if duration_seconds == 0:
        return m.REST_OF_DAY.render(translations)
    hours, remainder = divmod(duration_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    for value, message in ((hours, m.hour_count), (minutes, m.minute_count),
                           (seconds, m.second_count)):
        if value:
            parts.append(message(value).render(translations))
    return m.DURATION_LIST_SEPARATOR.render(translations).join(parts)


class Broker:
    def __init__(self, config_loader: Callable[[], Configuration], authorizer: Authorizer,
                 accounts: Accounts, preferences: Preferences | None = None,
                 extensions: Extensions | None = None, timer_usage: TimerUsage | None = None,
                 application_catalog: Callable[[UserAccount], tuple[dict, ...]] | None = None,
                 running_apps: RunningApps | None = None,
                 *, monotonic=time.monotonic,
                 now=lambda: datetime.now().astimezone(), caller_alive=lambda _sender: True,
                 whats_new_loader=WhatsNewCatalog.load):
        self._config_loader = config_loader
        self._authorizer = authorizer
        self._accounts = accounts
        self._preferences = preferences
        self._extensions = extensions
        self._timer_usage = timer_usage
        self._application_catalog = application_catalog
        self._running_apps = running_apps
        self._monotonic = monotonic
        self._now = now
        self._caller_alive = caller_alive
        self._whats_new_loader = whats_new_loader
        self._request_lock = threading.Lock()
        self._transaction_revision = 0
        self._rate_lock = threading.Lock()
        self._last_request = {}
        self._grant_diagnostics = GrantDiagnostics()

    def _acquire_request_lock(self):
        if not self._request_lock.acquire(blocking=False):
            return False
        self._transaction_revision += 1
        return True

    def _write_extension(self, uid, value):
        self._grant_diagnostics.write_started(uid)
        self._accounts.set_extension(uid, value)
        if self._accounts.get_extension(uid) != value:
            raise BackendFailure("extension verification failed")
        try:
            self._grant_diagnostics.wrote(uid, value)
            self._observe_grant(uid, *value)
        except Exception:
            get_logger("grant").warning("grant.invalid")

    def _observe_grant(self, uid, issued, duration, *, is_current=None):
        try:
            self._grant_diagnostics.observe(
                uid, (issued, duration), self._now(), self._monotonic(),
                is_current=is_current,
            )
        except Exception:
            # Diagnostics cannot turn a policy operation into a failure.
            get_logger("grant").warning("grant.invalid")

    def observe_grants(self):
        """Read live state after supported account-change signals or periodic checks."""
        revision = self._transaction_revision

        def is_current():
            return not self._request_lock.locked() and self._transaction_revision == revision

        if not is_current():
            return
        config = self._load_config()
        for account in self._accounts.list_users():
            if not is_current():
                return
            if self._eligible(config, account):
                value = self._accounts.get_extension(account.uid)
                self._observe_grant(account.uid, *value, is_current=is_current)

    def collect_extension_diagnostics(self) -> None:
        """Observe eligible child sessions without mutating saved policy."""
        if self._extensions is None:
            return
        config = self._load_config()
        self._extensions.collect_diagnostics(
            user.uid for user in self._accounts.list_users() if self._eligible(config, user))

    def refresh_enabled_extensions(self) -> tuple[int, ...]:
        """Reassert extension activation for every enabled managed child."""
        config = self._load_config()
        if self._preferences is None or self._extensions is None:
            raise BackendFailure("extension management is unavailable")
        try:
            users = self._accounts.list_users()
        except Exception as error:
            raise BackendFailure("managed accounts are unavailable") from error

        refreshed = []
        for user in users:
            if not self._eligible(config, user):
                continue
            try:
                preferences = self._preferences.load(user.uid)
                if preferences["parent_control_enabled"]:
                    # A live user bus notifies an existing Shell immediately;
                    # otherwise the setting is durable for the next session.
                    self._extensions.set_enabled(user.uid, True, recover_global_switch=True)
                    refreshed.append(user.uid)
            except Exception as error:
                LOG.error("core.001", error_type=error_code(error))
                raise BackendFailure("could not refresh the child extension") from error
        return tuple(refreshed)

    def calculate_remaining_time(
            self, caller_uid: int, target_uid: int,
            daily_allowance_remaining_seconds: int,
            one_time_grant_remaining_seconds: int,
            additional_one_time_grant_seconds: int) -> int:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot calculate time for this account")
        return calculate_active_extension_seconds(
            daily_allowance_remaining_seconds,
            one_time_grant_remaining_seconds,
            additional_one_time_grant_seconds,
        )

    def calculate_own_remaining_time(
            self, caller_uid: int,
            daily_allowance_remaining_seconds: int) -> int:
        """Combine a child's timer estimate with its broker-owned live grant."""
        config = self._load_config()
        target = self._target(config, caller_uid)
        try:
            grant_time, grant_duration = self._accounts.get_extension(target.uid)
        except Exception as error:
            raise BackendFailure("remaining-time grant is unavailable") from error
        if (type(grant_time) is not int or type(grant_duration) is not int or
                grant_time < 0 or not 0 <= grant_duration <= UINT32_MAX):
            raise BackendFailure("remaining-time grant is invalid")
        grant_remaining = max(
            0, grant_time + grant_duration - int(self._now().timestamp()),
        )
        if grant_remaining > UINT32_MAX:
            raise BackendFailure("remaining-time grant is invalid")
        return calculate_active_extension_seconds(
            daily_allowance_remaining_seconds, grant_remaining, 0,
        )

    def prepare_own_session(self, caller_uid: int) -> bool:
        """Restore expired-grant app policy when a child resumes its session.

        A parent may renew an expired grant while the child is at the lock
        screen. Serialize with approval and re-read ActiveExtension under the
        transaction lock so a current grant always wins and its applications
        remain untouched.
        """
        if not self._acquire_request_lock():
            raise Busy("another request is already in progress")
        try:
            config = self._load_config()
            target = self._target(config, caller_uid)
            try:
                grant_time, grant_duration = self._accounts.get_extension(target.uid)
            except Exception as error:
                raise BackendFailure("remaining-time grant is unavailable") from error
            if (type(grant_time) is not int or type(grant_duration) is not int or
                    grant_time < 0 or not 0 <= grant_duration <= UINT32_MAX):
                raise BackendFailure("remaining-time grant is invalid")

            now_seconds = int(self._now().timestamp())
            if grant_duration == 0:
                LOG.info("core.002")
                return False
            if grant_time + grant_duration > now_seconds:
                LOG.info("core.003")
                return False

            preferences = self._load_request_preferences(target.uid)
            desired_filter = (False, blocked_targets(preferences, False))
            termination_patterns = blocked_patterns(preferences, False)
            terminate_blocked_apps = bool(desired_filter[1] or termination_patterns)
            if terminate_blocked_apps:
                if self._running_apps is None:
                    raise BackendFailure("blocked application termination is unavailable")
                try:
                    self._running_apps.preflight(
                        target.uid, desired_filter[1], termination_patterns,
                    )
                except Exception as error:
                    raise BackendFailure(
                        "blocked applications could not be stopped"
                    ) from error

            old_filter = self._accounts.get_filter(target.uid)
            filter_changed = False
            termination_started = False
            try:
                LOG.info("core.004", blocked_target_count=len(desired_filter[1]))
                self._accounts.set_filter(target.uid, desired_filter)
                filter_changed = True
                if self._accounts.get_filter(target.uid) != desired_filter:
                    raise BackendFailure("app-filter verification failed")
                if terminate_blocked_apps:
                    termination_started = True
                    terminated = self._running_apps.terminate(
                        target.uid, desired_filter[1], termination_patterns,
                    )
                    if type(terminated) is not int or terminated < 0:
                        raise BackendFailure("blocked application termination failed")
                    LOG.info("core.005", count=terminated)
                LOG.info("core.006")
                return True
            except Exception as error:
                # Once termination starts, processes cannot be restored. Keep
                # the canonical strict filter active. Before that point,
                # preserve the exact policy that preceded reconciliation.
                record_exception(error)
                if filter_changed and not termination_started:
                    try:
                        self._accounts.set_filter(target.uid, old_filter)
                        if self._accounts.get_filter(target.uid) != old_filter:
                            raise RuntimeError("app-filter rollback read-back mismatch")
                    except Exception as rollback_error:
                        LOG.critical("core.007", error_type=error_code(rollback_error))
                        raise RollbackFailure(
                            "session app-filter rollback could not be verified"
                        ) from rollback_error
                LOG.warning(
                    "core.008",
                    error_type=error_code(error),
                    strict_filter=termination_started,
                )
                if isinstance(error, BrokerError):
                    raise
                raise BackendFailure("session application policy could not be prepared") from error
        finally:
            self._request_lock.release()

    def get_time_status(self, caller_uid: int, target_uid: int,
                        additional_seconds: int = 0) -> TimeStatus:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot inspect time for this account")
        return self._time_status(target.uid, additional_seconds)

    def has_running_soft_blocked_apps(self, caller_uid: int, target_uid: int) -> bool:
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        target = self._target(config, target_uid)
        preferences = self._load_request_preferences(target.uid)
        soft_preferences = {"apps": {
            app_id: entry for app_id, entry in preferences["apps"].items()
            if entry["state"] == "conditional"
        }}
        targets = blocked_targets(soft_preferences, False)
        patterns = blocked_patterns(soft_preferences, False)
        if not (targets or patterns):
            return False
        if self._running_apps is None:
            raise BackendFailure("running application status is unavailable")
        try:
            return self._running_apps.has_running(target.uid, targets, patterns)
        except Exception as error:
            raise BackendFailure("running application status is unavailable") from error

    def list_running_soft_blocked_apps(self, caller_uid: int, target_uid: int) -> tuple[str, ...]:
        """Return saved policy IDs for running soft apps, without changing state."""
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        target = self._target(config, target_uid)
        preferences = self._load_request_preferences(target.uid)
        running = []
        for app_id, entry in preferences["apps"].items():
            if entry["state"] != "conditional":
                continue
            policy = {"apps": {app_id: entry}}
            targets = blocked_targets(policy, False)
            patterns = blocked_patterns(policy, False)
            if not (targets or patterns):
                continue
            if self._running_apps is None:
                raise BackendFailure("running application status is unavailable")
            try:
                if self._running_apps.has_running(target.uid, targets, patterns):
                    running.append(app_id)
            except Exception as error:
                raise BackendFailure("running application status is unavailable") from error
        return tuple(sorted(running))

    def _time_status(self, target_uid: int, additional_seconds: int) -> TimeStatus:
        if self._preferences is None or self._timer_usage is None:
            raise BackendFailure("remaining-time status is unavailable")
        stage = "preferences"
        try:
            preferences = self._preferences.load(target_uid)
            stage = "usage"
            usage_entries = self._timer_usage.query_usage(target_uid)
            stage = "grant"
            grant_time, grant_duration = self._accounts.get_extension(target_uid)
        except Exception as error:
            LOG.warning("core.009", stage=stage, error_type=error_code(error))
            raise BackendFailure("remaining-time status is unavailable") from error

        return self._time_status_from_usage(
            preferences, usage_entries, grant_time, grant_duration, additional_seconds,
        )

    def _time_status_from_usage(
            self, preferences: dict, usage_entries: tuple[tuple[int, int], ...],
            grant_time: int, grant_duration: int, additional_seconds: int,
            evaluated_at: datetime | None = None) -> TimeStatus:
        now = evaluated_at or self._now()
        now_seconds = int(now.timestamp())
        daily_limit_seconds = (
            preferences["daily_time_limit_minutes"] * 60
            if preferences["parent_control_enabled"] else 0
        )
        start_of_today = datetime.combine(
            now.date(), datetime.min.time(), tzinfo=now.tzinfo,
        )
        start_of_today_seconds = int(start_of_today.timestamp())
        today_intervals = []
        for start, end in usage_entries:
            if (type(start) is not int or type(end) is not int or
                    start < 0 or end < start):
                raise BackendFailure("timer usage returned an invalid interval")
            clipped_start = max(start, start_of_today_seconds)
            clipped_end = min(end, now_seconds)
            if clipped_end > clipped_start:
                today_intervals.append((clipped_start, clipped_end))
        used_today = 0
        merged_end = 0
        for start, end in sorted(today_intervals):
            if start >= merged_end:
                used_today += end - start
            elif end > merged_end:
                used_today += end - merged_end
            merged_end = max(merged_end, end)
        daily_remaining = max(0, daily_limit_seconds - used_today)
        grant_remaining = max(0, grant_time + grant_duration - now_seconds)
        calculated = calculate_active_extension_seconds(
            daily_remaining, grant_remaining, additional_seconds,
        )
        return TimeStatus(
            daily_remaining, grant_remaining, additional_seconds, calculated,
        )

    @staticmethod
    def _check_caller(config: Configuration, caller_uid: int) -> None:
        if caller_uid != config.kiosk_uid:
            raise AccessDenied("caller is not the configured request station")

    @staticmethod
    def _eligible(config: Configuration, user: UserAccount) -> bool:
        return (
            MIN_MANAGED_UID <= user.uid <= UINT32_MAX and
            user.uid != config.kiosk_uid and
            user.is_local and not user.is_system and not user.is_admin
        )

    def _is_admin(self, caller_uid: int) -> bool:
        if caller_uid == 0:
            return True
        try:
            user = self._accounts.get_user(caller_uid)
            return user.is_admin and user.is_local
        except Exception:
            return False

    def _can_manage_or_kiosk(self, config: Configuration, caller_uid: int) -> bool:
        return caller_uid == config.kiosk_uid or self._is_admin(caller_uid)

    def list_managed_users(self, caller_uid: int) -> tuple[UserAccount, ...]:
        config = self._load_config()
        if not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller is not an administrator or request station")
        users = (user for user in self._accounts.list_users() if self._eligible(config, user))
        return tuple(sorted(users, key=lambda user: (user.label.casefold(), user.uid)))

    def list_kiosk_users(self, caller_uid: int) -> tuple[UserAccount, ...]:
        """Read-only child discovery, including while upgrade policy is gated."""
        self._check_caller(self._load_config(), caller_uid)
        return self.list_managed_users(caller_uid)

    def clear_live_session_runtime_caps(self) -> tuple[int, ...]:
        """Drop login-time systemd kill timers on live managed child sessions."""
        config = self._load_config()
        cleared = []
        for user in self._accounts.list_users():
            if not self._eligible(config, user):
                continue
            if self._accounts.clear_session_runtime_max(user.uid):
                cleared.append(user.uid)
        return tuple(cleared)

    def get_own_account(self, caller_uid: int) -> UserAccount:
        """Return the managed child identity of the calling session."""
        config = self._load_config()
        try:
            user = self._accounts.get_user(caller_uid)
        except Exception as error:
            raise BackendFailure("caller account is unavailable") from error
        if not self._eligible(config, user):
            raise AccessDenied("caller is not a managed child")
        return user

    @staticmethod
    def _eligible_approver(config: Configuration, user: UserAccount) -> bool:
        return (
            MIN_MANAGED_UID <= user.uid <= UINT32_MAX and
            user.uid != config.kiosk_uid and
            user.is_local and not user.is_system and not user.is_locked and
            user.is_admin and user.is_interactive and
            bool(APPROVER_USERNAME_RE.fullmatch(user.username))
        )

    def list_approvers(self, caller_uid: int) -> tuple[UserAccount, ...]:
        config = self._load_config()
        # A managed child may select the administrator who will be asked to
        # approve its own request.  The Polkit rule still restricts the
        # resulting challenge to that identity; this endpoint never grants
        # authorization or exposes account-management operations.
        caller_is_managed_child = False
        try:
            caller_is_managed_child = self._eligible(
                config, self._accounts.get_user(caller_uid)
            )
        except Exception:
            pass
        if not (self._can_manage_or_kiosk(config, caller_uid) or caller_is_managed_child):
            raise AccessDenied("caller cannot select an approving administrator")
        users = (
            user for user in self._accounts.list_users()
            if self._eligible_approver(config, user)
        )
        return tuple(sorted(users, key=lambda user: (user.label.casefold(), user.uid)))

    def authorize_diagnostic_export(self, caller_uid: int) -> None:
        """All product front ends may review the same bounded diagnostic archive."""
        config = self._load_config()
        if self._can_manage_or_kiosk(config, caller_uid):
            return
        try:
            user = self._accounts.get_user(caller_uid)
        except Exception as error:
            raise AccessDenied("caller cannot export diagnostic logs") from error
        if not self._eligible(config, user):
            raise AccessDenied("caller cannot export diagnostic logs")

    def authorize_log_component(self, caller_uid: int, component: str) -> None:
        """Ensure a front end can write only to its own component log."""
        config = self._load_config()
        if component == "parent" and self._is_admin(caller_uid):
            return
        if component == "kiosk" and caller_uid == config.kiosk_uid:
            return
        if component == "child":
            try:
                user = self._accounts.get_user(caller_uid)
            except Exception as error:
                raise AccessDenied("caller cannot write this component log") from error
            if self._eligible(config, user):
                return
        raise AccessDenied("caller cannot write this component log")

    def _authorize_own_language(self, caller_uid: int) -> None:
        config = self._load_config()
        if type(caller_uid) is not int or not 0 <= caller_uid <= UINT32_MAX:
            raise AccessDenied("invalid caller identity")
        if self._can_manage_or_kiosk(config, caller_uid):
            return
        try:
            user = self._accounts.get_user(caller_uid)
        except Exception as error:
            raise AccessDenied("caller cannot select a language") from error
        if not self._eligible(config, user):
            raise AccessDenied("caller cannot select a language")

    def _own_whats_new_component(self, caller_uid: int) -> str:
        config = self._load_config()
        if type(caller_uid) is not int or not 0 <= caller_uid <= UINT32_MAX:
            raise AccessDenied("invalid caller identity")
        if caller_uid == config.kiosk_uid:
            raise AccessDenied("kiosk must select a child")
        if self._is_admin(caller_uid):
            return "Parent"
        self._target(config, caller_uid)
        return "Child"

    def get_own_whats_new(self, caller_uid: int) -> dict:
        component = self._own_whats_new_component(caller_uid)
        return self._whats_new(caller_uid, component)

    def get_child_whats_new(self, caller_uid: int, target_uid: int) -> dict:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._whats_new(target_uid, "Child")

    def acknowledge_own_whats_new(self, caller_uid: int, version: object) -> dict:
        component = self._own_whats_new_component(caller_uid)
        return self._whats_new(caller_uid, component, acknowledge=version)

    def acknowledge_child_whats_new(self, caller_uid: int, target_uid: int, version: object) -> dict:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._whats_new(target_uid, "Child", acknowledge=version)

    def _whats_new(self, uid: int, component: str, *, acknowledge=_NO_ACKNOWLEDGEMENT) -> dict:
        if self._preferences is None:
            raise BackendFailure("release acknowledgement store is unavailable")
        try:
            catalog = self._whats_new_loader()
        except (WhatsNewError, OSError) as error:
            raise BackendFailure("release metadata is unavailable") from error
        if acknowledge is not _NO_ACKNOWLEDGEMENT:
            try:
                record_id = catalog.acknowledgement(component, acknowledge)
            except WhatsNewError as error:
                raise InvalidRequest("release is unavailable for this component") from error
        try:
            if acknowledge is _NO_ACKNOWLEDGEMENT:
                seen = self._preferences.load(uid)["personal"].get("whats_new_seen", [])
            else:
                seen = self._preferences.acknowledge_whats_new(uid, record_id, catalog.retained_records)
        except (PreferencesError, OSError) as error:
            raise BackendFailure("release acknowledgements are unavailable") from error
        return catalog.available(component, seen)

    def get_own_language(self, caller_uid: int) -> str:
        self._authorize_own_language(caller_uid)
        if self._preferences is None:
            raise BackendFailure("user language store is unavailable")
        try:
            return self._preferences.load(caller_uid)["personal"]["language"]
        except (PreferencesError, OSError) as error:
            raise BackendFailure("user language is unavailable") from error

    def set_own_language(self, caller_uid: int, language: object) -> str:
        self._authorize_own_language(caller_uid)
        return self._save_language(caller_uid, language)

    def get_own_time_grant_presets(self, caller_uid: int) -> list[int]:
        self._target(self._load_config(), caller_uid)
        return self._load_time_grant_presets(caller_uid)

    def get_child_time_grant_presets(self, caller_uid: int, target_uid: int) -> list[int]:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._load_time_grant_presets(target_uid)

    def _load_time_grant_presets(self, target_uid: int) -> list[int]:
        if self._preferences is None:
            raise BackendFailure("time grant preset store is unavailable")
        try:
            return self._preferences.load(target_uid)["personal"]["time_grant_presets"]
        except (PreferencesError, OSError) as error:
            raise BackendFailure("time grant presets are unavailable") from error

    def set_own_time_grant_presets(self, caller_uid: int, presets: object) -> list[int]:
        self._target(self._load_config(), caller_uid)
        return self._save_time_grant_presets(caller_uid, presets)

    def set_child_time_grant_presets(self, caller_uid: int, target_uid: int, presets: object) -> list[int]:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._save_time_grant_presets(target_uid, presets)

    def _save_time_grant_presets(self, target_uid: int, presets: object) -> list[int]:
        try:
            presets = validate_time_grant_presets(presets)
        except PreferencesError as error:
            raise InvalidRequest("invalid time grant presets") from error
        if self._preferences is None:
            raise BackendFailure("time grant preset store is unavailable")
        try:
            return self._preferences.update_time_grant_presets(target_uid, presets)
        except (PreferencesError, OSError) as error:
            raise BackendFailure("could not save time grant presets") from error

    def get_own_notifications(self, caller_uid: int) -> dict:
        self._target(self._load_config(), caller_uid)
        return self._load_notifications(caller_uid)

    def get_child_notifications(self, caller_uid: int, target_uid: int) -> dict:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._load_notifications(target_uid)

    def _load_notifications(self, target_uid: int) -> dict:
        if self._preferences is None:
            raise BackendFailure("notification store is unavailable")
        try:
            return self._preferences.load(target_uid)["personal"]["notifications"]
        except (PreferencesError, OSError) as error:
            raise BackendFailure("notifications are unavailable") from error

    def get_own_session_allows_soft_apps(self, caller_uid: int) -> bool:
        """Read current policy, independently of the next request's checkbox."""
        target = self._target(self._load_config(), caller_uid)
        if not self._acquire_request_lock():
            raise Busy("another request is already in progress")
        try:
            preferences = self._load_request_preferences(target.uid)
            try:
                live = self._accounts.get_filter(target.uid)
                hard = (False, blocked_targets(preferences, True))
                strict = (False, blocked_targets(preferences, False))
                if live != hard:
                    return False
                if hard != strict:
                    return True
                # With no distinct soft targets the filters are identical.
                # The active grant and its remembered choice supply the intent.
                issued, duration = self._accounts.get_extension(target.uid)
                return (duration > 0 and issued + duration > int(self._now().timestamp())
                        and preferences["request"]["allow_soft_blocked_apps"])
            except Exception as error:
                raise BackendFailure("session application policy is unavailable") from error
        finally:
            self._request_lock.release()

    def set_own_notifications(self, caller_uid: int, notifications: object) -> dict:
        self._target(self._load_config(), caller_uid)
        return self._save_notifications(caller_uid, notifications)

    def set_child_notifications(self, caller_uid: int, target_uid: int, notifications: object) -> dict:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._save_notifications(target_uid, notifications)

    def _save_notifications(self, target_uid: int, notifications: object) -> dict:
        try:
            notifications = validate_notifications(notifications)
        except PreferencesError as error:
            raise InvalidRequest("invalid notification preferences") from error
        if self._preferences is None:
            raise BackendFailure("notification store is unavailable")
        try:
            return self._preferences.update_notifications(target_uid, notifications)
        except (PreferencesError, OSError) as error:
            raise BackendFailure("could not save notifications") from error

    def _kiosk_language_target(self, caller_uid: int, target_uid: int) -> int:
        config = self._load_config()
        if type(caller_uid) is not int or caller_uid != config.kiosk_uid:
            raise AccessDenied("kiosk access is required")
        return self._target(config, target_uid).uid

    def get_child_language(self, caller_uid: int, target_uid: int) -> str:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        if self._preferences is None:
            raise BackendFailure("user language store is unavailable")
        try:
            return self._preferences.load(target_uid)["personal"]["language"]
        except (PreferencesError, OSError) as error:
            raise BackendFailure("user language is unavailable") from error

    def get_child_language_context(self, caller_uid: int, target_uid: int) -> tuple[str, str]:
        """Return saved intent and the selected child's desktop fallback."""
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        language = self.get_child_language(caller_uid, target_uid)
        try:
            desktop_language = self._accounts.get_user(target_uid).desktop_language
        except Exception as error:
            raise BackendFailure("child desktop language is unavailable") from error
        return language, desktop_language

    def set_child_language(self, caller_uid: int, target_uid: int, language: object) -> str:
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        return self._save_language(target_uid, language)

    def _save_language(self, target_uid: int, language: object) -> str:
        try:
            language = validate_language(language)
        except PreferencesError as error:
            raise InvalidRequest("invalid language selection") from error
        if self._preferences is None:
            raise BackendFailure("user language store is unavailable")
        try:
            return self._preferences.update_language(target_uid, language)
        except (PreferencesError, OSError) as error:
            raise BackendFailure("could not save user language") from error

    def _target(self, config: Configuration, target_uid: int) -> UserAccount:
        if type(target_uid) is not int or not 0 <= target_uid <= UINT32_MAX:
            raise InvalidRequest("target UID is invalid")
        try:
            user = self._accounts.get_user(target_uid)
        except Exception as error:
            raise InvalidRequest("selected account is unavailable") from error
        if not self._eligible(config, user):
            raise AccessDenied("selected account is not an eligible standard account")
        return user

    def _approver(self, config: Configuration, approver_uid: int) -> UserAccount:
        if type(approver_uid) is not int or not 0 <= approver_uid <= UINT32_MAX:
            raise InvalidRequest("approver UID is invalid")
        try:
            user = self._accounts.get_user(approver_uid)
        except Exception as error:
            raise InvalidRequest("selected approver is unavailable") from error
        if not self._eligible_approver(config, user):
            raise AccessDenied("selected approver is not an eligible administrator")
        return user

    def get_preferences(self, caller_uid: int, target_uid: int) -> dict:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot read this account")
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            return self._preferences.load(target.uid)
        except PreferencesError as error:
            raise BackendFailure("preferences are unavailable") from error

    def list_applications(self, caller_uid: int, target_uid: int) -> tuple[dict, ...]:
        """List the selected child's launchers for the administrator UI."""
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        target = self._target(config, target_uid)
        if self._application_catalog is None:
            raise BackendFailure("application catalog is unavailable")
        try:
            applications = self._application_catalog(target)
            candidates = desktop_language_candidates(self.get_own_language(caller_uid))
            localized = []
            for application in applications:
                app = dict(application)
                for field, translations in (("name", "localized_names"),
                                            ("description", "localized_descriptions")):
                    values = app.get(translations, {})
                    app[field] = next((values[locale] for locale in candidates
                                       if values.get(locale)), app[field])
                localized.append(app)
            return tuple(sorted(localized, key=lambda app: app["name"].casefold()))
        except Exception as error:
            raise BackendFailure("application catalog is unavailable") from error

    def _refresh_application_targets(self, target: UserAccount,
                                     preferences: dict) -> dict:
        """Replace UI-cached targets with the child's current launcher targets."""
        if self._application_catalog is None:
            return preferences
        try:
            applications = self._application_catalog(target)
            current_targets = {
                application["id"]: list(application["targets"])
                for application in applications
            }
            replacements = replacement_policy_ids(preferences["apps"], applications)
            for desktop_id, previous_id in replacements.items():
                preferences["apps"][desktop_id] = preferences["apps"].pop(previous_id)
            for desktop_id, policy in preferences["apps"].items():
                if desktop_id in current_targets:
                    policy["targets"] = current_targets[desktop_id]
            return validate_preferences(preferences)
        except Exception as error:
            raise BackendFailure("application catalog is unavailable") from error

    def set_preferences(self, caller_uid: int, target_uid: int, value: object) -> dict:
        if not self._acquire_request_lock():
            raise Busy("another request is already in progress")
        try:
            return self._set_preferences_locked(caller_uid, target_uid, value)
        finally:
            self._request_lock.release()

    def _set_preferences_locked(
            self, caller_uid: int, target_uid: int, value: object) -> dict:
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        target = self._target(config, target_uid)
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            current = self._preferences.load(target.uid)
        except PreferencesError as error:
            raise BackendFailure("preferences are unavailable") from error
        try:
            requested = validate_preferences(value)
        except PreferencesError as error:
            raise InvalidRequest(str(error)) from error
        # The dedicated toggle operation owns installation state.
        requested["parent_control_enabled"] = current["parent_control_enabled"]
        # Personal choices belong to the child, not the policy editor.
        requested["personal"] = current["personal"]
        # The parent window may have remained open while an application
        # self-updated and replaced its versioned executable. Resolve the
        # selected desktop IDs again at commit time so neither the saved
        # Malcontent target nor the execution rule points at a vanished file.
        requested = self._refresh_application_targets(target, requested)
        try:
            old_filter = self._accounts.get_filter(target.uid)
        except Exception as error:
            raise BackendFailure("app filter is unavailable") from error
        desired_filter = (False, blocked_targets(requested, False))
        current_hard_targets = set(blocked_targets(current, True))
        current_blocked_targets = set(blocked_targets(current, False))
        requested_hard_targets = set(blocked_targets(requested, True))
        requested_blocked_targets = set(desired_filter[1])
        termination_targets = tuple(sorted(
            (requested_hard_targets - current_hard_targets) |
            ((requested_blocked_targets - requested_hard_targets) -
             current_blocked_targets)
        ))
        current_hard_patterns = set(blocked_patterns(current, True))
        current_blocked_patterns = set(blocked_patterns(current, False))
        requested_hard_patterns = set(blocked_patterns(requested, True))
        requested_blocked_patterns = set(blocked_patterns(requested, False))
        termination_patterns = tuple(sorted(
            (requested_hard_patterns - current_hard_patterns) |
            ((requested_blocked_patterns - requested_hard_patterns) -
             current_blocked_patterns)
        ))
        terminate_blocked_apps = bool(termination_targets or termination_patterns)
        if terminate_blocked_apps:
            if self._running_apps is None:
                raise BackendFailure("blocked application termination is unavailable")
            try:
                self._running_apps.preflight(
                    target.uid, termination_targets, termination_patterns,
                )
            except Exception as error:
                raise BackendFailure(
                    "blocked applications could not be stopped"
                ) from error
        LOG.info(
            "core.010",
            blocked_target_count=len(desired_filter[1]),
            newly_blocked_target_count=len(termination_targets),
            newly_blocked_pattern_count=len(termination_patterns),
            terminate_blocked_apps=terminate_blocked_apps,
        )
        preferences_saved = False
        termination_started = False
        try:
            # Persist first so AccountsService's synchronous execution-policy
            # reconciliation compiles the matching canonical patterns with the
            # new AppFilter.  If anything below fails, restore both sources.
            saved = self._preferences.save(target.uid, requested)
            preferences_saved = True
            self._accounts.set_filter(target.uid, desired_filter)
            if self._accounts.get_filter(target.uid) != desired_filter:
                raise BackendFailure("app-filter verification failed")
            sync = getattr(self._accounts, "sync_execution_policy", None)
            if sync is not None:
                sync()
            if terminate_blocked_apps:
                termination_started = True
                terminated = self._running_apps.terminate(
                    target.uid, termination_targets, termination_patterns,
                )
                if type(terminated) is not int or terminated < 0:
                    raise BackendFailure("blocked application termination failed")
                LOG.info("core.011", count=terminated)
            LOG.info("core.012")
            return saved
        except Exception as error:
            # Once termination starts, an exited process cannot be restored.
            # Retain the requested canonical policy so every requested block
            # remains enforced and its patterns remain available to the
            # execution-policy reconciler.
            record_exception(error)
            if termination_started:
                LOG.warning("core.013", error_type=error_code(error))
                if isinstance(error, BrokerError):
                    raise
                raise BackendFailure(
                    "blocked applications could not be stopped"
                ) from error
            LOG.warning("core.014", error_type=error_code(error))
            try:
                if preferences_saved:
                    self._preferences.save(target.uid, current)
                self._accounts.set_filter(target.uid, old_filter)
                if self._accounts.get_filter(target.uid) != old_filter:
                    raise RuntimeError("app-filter rollback read-back mismatch")
            except Exception as rollback_error:
                LOG.critical("core.015", error_type=error_code(rollback_error))
                raise RollbackFailure(
                    "app-filter rollback could not be verified"
                ) from rollback_error
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("app filter could not be applied") from error

    def update_request_preferences(self, caller_uid: int, target_uid: int,
                                   selected: str, custom: float,
                                   allow_soft: bool,
                                   last_selected_approver_uid: int = 0,
                                   custom_unit: str = "minutes") -> dict:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot update this account")
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            return self._preferences.update_request(
                target.uid, selected, custom, allow_soft,
                last_selected_approver_uid, custom_unit,
            )
        except PreferencesError as error:
            raise InvalidRequest(str(error)) from error

    def set_request_muted(self, caller_uid: int, target_uid: int, surface: str,
                          muted: bool) -> dict:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot update this account")
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            return self._preferences.update_request_muted(target.uid, surface, muted)
        except PreferencesError as error:
            raise InvalidRequest(str(error)) from error

    def set_parent_control(self, caller_uid: int, target_uid: int, enabled: bool,
                           daily_limit_minutes: int) -> dict:
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        if type(enabled) is not bool:
            raise InvalidRequest("enabled state must be boolean")
        if (type(daily_limit_minutes) is not int or not
                MIN_DAILY_LIMIT_MINUTES <= daily_limit_minutes <= MAX_DAILY_LIMIT_MINUTES):
            raise InvalidRequest(
                "daily time limit must be an integer from 0 to 1440 minutes"
            )
        target = self._target(config, target_uid)
        LOG.info("core.016", enabled=enabled, daily_limit_minutes=daily_limit_minutes)
        if self._preferences is None or self._extensions is None:
            raise BackendFailure("extension management is unavailable")
        try:
            current = self._preferences.load(target.uid)
            previous = current["parent_control_enabled"]
            desired_filter = (False, blocked_targets(current, False))
            # Known rendering failures must not toggle the extension, clear a
            # grant, or change time limits before an inevitable failed save.
            # Commit still reconciles again: this is not a filesystem lock.
            self._accounts.validate_filter(target.uid, desired_filter)
            old_limit_type = self._accounts.get_limit_type(target.uid)
            old_daily_limit = self._accounts.get_daily_limit(target.uid)
            old_filter = self._accounts.get_filter(target.uid)
            old_extension = self._accounts.get_extension(target.uid)
            extension_changed = enabled != previous
            if extension_changed:
                self._extensions.set_enabled(target.uid, enabled)
            try:
                desired_limit_type = DAILY_LIMIT_FLAG if enabled else 0
                desired_daily_limit = daily_limit_minutes * 60 if enabled else 0
                # App access is independent from screen time. Reapply the
                # saved blocklist so a toggle cannot retain a temporary
                # soft-block exception (or another stale live filter).
                if not enabled:
                    self._accounts.set_limit_type(target.uid, desired_limit_type)
                self._accounts.set_daily_limit(target.uid, desired_daily_limit)
                if extension_changed:
                    self._write_extension(target.uid, (0, 0))
                if enabled:
                    self._accounts.set_limit_type(target.uid, desired_limit_type)
                self._accounts.set_filter(target.uid, desired_filter)

                if (self._accounts.get_limit_type(target.uid) != desired_limit_type or
                        self._accounts.get_daily_limit(target.uid) != desired_daily_limit):
                    raise BackendFailure("parent-control account verification failed")
                if self._accounts.get_filter(target.uid) != desired_filter:
                    raise BackendFailure("app-filter verification failed")
                if (extension_changed and
                        self._accounts.get_extension(target.uid) != (0, 0)):
                    raise BackendFailure("parent-control account verification failed")

                current["parent_control_enabled"] = enabled
                current["daily_time_limit_minutes"] = daily_limit_minutes
                saved = self._preferences.save(target.uid, current)
                LOG.info("core.017", enabled=enabled)
                return saved
            except Exception as error:
                LOG.warning("core.018", error_type=error_code(error))
                record_exception(error)
                rollback_error = None
                try:
                    self._restore(
                        target.uid, old_limit_type, old_daily_limit, old_filter,
                        old_extension, None,
                    )
                except Exception as caught:
                    record_exception(caught)
                    rollback_error = caught
                try:
                    if extension_changed:
                        self._extensions.set_enabled(target.uid, previous)
                except Exception as caught:
                    record_exception(caught)
                    rollback_error = rollback_error or caught
                if rollback_error is not None:
                    LOG.critical("core.019", error_type=error_code(rollback_error))
                    raise RollbackFailure(
                        "parent-control rollback could not be verified"
                    ) from rollback_error
                raise error
        except ExecutionPolicyError as error:
            raise BackendFailure(
                "Could not prepare application blocking rules. Review App Limits: "
                "a wildcard folder may contain an unsupported file or folder name "
                "(such as spaces or commas)."
            ) from error
        except (OSError, RuntimeError, PreferencesError) as error:
            if isinstance(error, RollbackFailure):
                raise
            raise BackendFailure("could not change parent-control state") from error

    def revoke_one_time_grant(self, caller_uid: int, target_uid: int) -> None:
        """Remove a live grant and stop the selected child's blocked apps."""
        if not self._acquire_request_lock():
            raise Busy("another request is already in progress")
        try:
            LOG.info("core.020")
            config = self._load_config()
            if not self._is_admin(caller_uid):
                raise AccessDenied("administrator access is required")
            target = self._target(config, target_uid)
            preferences = self._load_request_preferences(target.uid)
            desired_filter = (False, blocked_targets(preferences, False))
            termination_patterns = blocked_patterns(preferences, False)
            terminate_blocked_apps = bool(
                desired_filter[1] or termination_patterns
            )
            if terminate_blocked_apps:
                if self._running_apps is None:
                    raise BackendFailure("blocked application termination is unavailable")
                try:
                    self._running_apps.preflight(
                        target.uid, desired_filter[1], termination_patterns,
                    )
                except Exception as error:
                    raise BackendFailure(
                        "blocked applications could not be stopped"
                    ) from error
            try:
                old_filter = self._accounts.get_filter(target.uid)
                old_extension = self._accounts.get_extension(target.uid)
            except Exception as error:
                LOG.warning("core.021", error_type=error_code(error))
                raise BackendFailure("one-time grant state is unavailable") from error
            termination_may_have_changed_processes = False
            try:
                self._accounts.set_filter(target.uid, desired_filter)
                if self._accounts.get_filter(target.uid) != desired_filter:
                    raise BackendFailure("app-filter verification failed")
                if terminate_blocked_apps:
                    termination_may_have_changed_processes = True
                    terminated = self._running_apps.terminate(
                        target.uid, desired_filter[1], termination_patterns,
                    )
                    if type(terminated) is not int or terminated < 0:
                        raise BackendFailure("blocked application termination failed")
                    termination_may_have_changed_processes = terminated > 0
                    LOG.info("core.022", count=terminated)
                self._write_extension(target.uid, (0, 0))
                if self._accounts.get_extension(target.uid) != (0, 0):
                    raise BackendFailure("extension verification failed")
                self._observe_grant(target.uid, 0, 0)
                LOG.info("core.023")
            except Exception as error:
                LOG.warning("core.024", error_type=error_code(error))
                record_exception(error)
                try:
                    self._write_extension(target.uid, old_extension)
                    rollback_filter = (
                        desired_filter
                        if termination_may_have_changed_processes
                        else old_filter
                    )
                    self._accounts.set_filter(target.uid, rollback_filter)
                    if (self._accounts.get_extension(target.uid) != old_extension or
                            self._accounts.get_filter(target.uid) != rollback_filter):
                        raise RuntimeError("rollback read-back mismatch")
                except Exception as rollback_error:
                    LOG.critical("core.025", error_type=error_code(rollback_error))
                    raise RollbackFailure(
                        "one-time grant rollback could not be verified"
                    ) from rollback_error
                if isinstance(error, BrokerError):
                    raise
                raise BackendFailure("one-time grant could not be revoked") from error
        finally:
            self._request_lock.release()

    def request_access(self, caller_uid: int, sender: str, target_uid: int,
                       approver_uid: int, duration_seconds: int,
                       allow_soft_blocked_apps: bool) -> tuple[str, str]:
        correlation_id, outcome, _granted_duration = self._request_access(
            "kiosk", caller_uid, sender, target_uid, approver_uid,
            duration_seconds, allow_soft_blocked_apps,
        )
        return correlation_id, outcome

    def request_own_access(self, caller_uid: int, sender: str,
                           approver_uid: int, duration_seconds: int,
                           allow_soft_blocked_apps: bool) -> tuple[str, str, int]:
        return self._request_access(
            "child", caller_uid, sender, caller_uid, approver_uid,
            duration_seconds, allow_soft_blocked_apps,
        )

    def _request_access(self, request_kind: str, caller_uid: int, sender: str,
                        target_uid: int, approver_uid: int,
                        duration_seconds: int,
                        allow_soft_blocked_apps: bool) -> tuple[str, str, int]:
        correlation_id = str(uuid.uuid4())
        if not self._acquire_request_lock():
            raise Busy("another request is already in progress")
        try:
            config = self._load_config()
            if request_kind == "kiosk":
                self._check_caller(config, caller_uid)
            elif request_kind != "child":
                raise BackendFailure("request kind is invalid")
            if type(duration_seconds) is not int or not (
                duration_seconds == 0 or
                MIN_REQUEST_SECONDS <= duration_seconds <= MAX_REQUEST_SECONDS
            ):
                raise InvalidRequest("duration is outside the supported range")
            if type(allow_soft_blocked_apps) is not bool:
                raise InvalidRequest("allow-soft value must be boolean")
            target = self._target(config, target_uid)
            if request_kind == "child" and caller_uid != target.uid:
                raise AccessDenied("a child can request access only for itself")
            approver = self._approver(config, approver_uid)
            preferences = self._load_request_preferences(target.uid)
            desired_filter = (
                False,
                blocked_targets(preferences, allow_soft_blocked_apps),
            )
            termination_patterns = (
                () if allow_soft_blocked_apps else blocked_patterns(preferences, False)
            )
            if request_kind == "child" and not preferences["parent_control_enabled"]:
                raise AccessDenied("parent control is not enabled for this account")
            # Check before prompting so a recent grant is rejected without a
            # new authorization dialog. Denied and cancelled attempts do not
            # consume the interval; only a completed grant records it below.
            self._apply_rate_limit(caller_uid, config.minimum_request_interval_seconds)
            LOG.info(
                "core.026",
                request=correlation_id,
                duration_seconds=duration_seconds,
                allow_soft=allow_soft_blocked_apps,
                kind=request_kind,
            )

            language = (self.get_own_language(caller_uid) if request_kind == "child"
                        else self.get_child_language(caller_uid, target.uid))
            translations = (load_translations(language, (target.desktop_language,))
                            if not language and request_kind == "kiosk" else
                            load_translations(language))
            template = (m.POLKIT_GRANT_SOFT_APPS if allow_soft_blocked_apps
                        else m.POLKIT_GRANT)
            # Polkit expands details once, after translation. Keep the account
            # label in its own detail so literal $(...) in user data cannot be
            # interpreted as message properties.
            message = (template % {
                "target": "$(target-account)",
                "duration": format_requested_duration(duration_seconds, translations),
            }).render(translations)
            outcome = self._authorizer.check(
                request_kind, sender, correlation_id, target.label, approver.username,
                message,
            )
            if outcome not in {"approved", "denied", "cancelled"}:
                raise BackendFailure("authorizer returned an invalid outcome")
            if outcome != "approved":
                LOG.info("core.027", request=correlation_id, outcome=outcome)
                return correlation_id, outcome, 0
            if not self._caller_alive(sender):
                LOG.warning("core.028", request=correlation_id)
                return correlation_id, "denied", 0
            # Fail closed if the selected account changed while the parent was
            # authenticating (including an AccountType promotion to admin), or
            # if the selected approver is no longer an eligible administrator.
            if self._target(config, target_uid) != target:
                raise AccessDenied("selected account changed during authorization")
            if self._approver(config, approver_uid) != approver:
                raise AccessDenied("selected approver changed during authorization")
            if self._load_request_preferences(target.uid) != preferences:
                raise AccessDenied("preferences changed during authorization")

            if duration_seconds == 0:
                issued_at_time = self._now()
                duration = seconds_until_local_midnight(issued_at_time)
                LOG.info("core.grant-rest-of-day", request=correlation_id, calculated=duration)
            else:
                if self._preferences is None or self._timer_usage is None:
                    raise BackendFailure("remaining-time status is unavailable")
                LOG.info("core.029", request=correlation_id)
                try:
                    usage_entries = self._timer_usage.query_usage_as(target.uid, approver)
                except Exception as error:
                    category = getattr(error, "category", type(error).__name__)
                    LOG.warning("core.030", request=correlation_id, error=category)
                    raise BackendFailure("remaining-time status is unavailable") from error
                LOG.info("core.031", request=correlation_id)

                # Fail closed before consuming a result obtained under an
                # identity which may have changed during the helper call.
                if not self._caller_alive(sender):
                    LOG.warning("core.028", request=correlation_id)
                    return correlation_id, "denied", 0
                if self._target(config, target_uid) != target:
                    raise AccessDenied("selected account changed during authorization")
                if self._approver(config, approver_uid) != approver:
                    raise AccessDenied("selected approver changed during authorization")
                if self._load_request_preferences(target.uid) != preferences:
                    raise AccessDenied("preferences changed during authorization")

                try:
                    grant_time, grant_duration = self._accounts.get_extension(target.uid)
                except Exception as error:
                    raise BackendFailure("remaining-time status is unavailable") from error
                issued_at_time = self._now()
                self._observe_grant(target.uid, grant_time, grant_duration)
                status = self._time_status_from_usage(
                    preferences, usage_entries, grant_time, grant_duration,
                    duration_seconds, issued_at_time,
                )
                duration = status.calculated_active_extension_seconds
                LOG.info("core.grant-calculation", request=correlation_id,
                         daily=status.daily_allowance_remaining_seconds,
                         grant=status.one_time_grant_remaining_seconds,
                         additional=duration_seconds, calculated=duration)

            # The identity-scoped query may take up to the backend timeout.
            # Revalidate again immediately before privileged account writes.
            if not self._caller_alive(sender):
                LOG.warning("core.028", request=correlation_id)
                return correlation_id, "denied", 0
            if self._target(config, target_uid) != target:
                raise AccessDenied("selected account changed during authorization")
            if self._approver(config, approver_uid) != approver:
                raise AccessDenied("selected approver changed during authorization")
            if self._load_request_preferences(target.uid) != preferences:
                raise AccessDenied("preferences changed during request")
            issued_at = int(issued_at_time.timestamp())
            if issued_at <= 0 or issued_at > (1 << 64) - 1 or not 0 < duration <= UINT32_MAX:
                raise BackendFailure("calculated extension is outside the supported range")
            terminate_blocked_apps = (
                not allow_soft_blocked_apps and
                (bool(desired_filter[1]) or bool(termination_patterns))
            )
            if terminate_blocked_apps:
                if self._running_apps is None:
                    raise BackendFailure("blocked application termination is unavailable")
                try:
                    self._running_apps.preflight(
                        target.uid, desired_filter[1], termination_patterns,
                    )
                except Exception as error:
                    raise BackendFailure(
                        "blocked applications could not be stopped"
                    ) from error
            self._apply(
                target.uid, preferences, desired_filter,
                (issued_at, duration), correlation_id,
                termination_patterns if terminate_blocked_apps else None,
            )
            self._record_rate_limit(caller_uid)
            LOG.info("core.032", request=correlation_id)
            return correlation_id, "approved", duration
        finally:
            self._request_lock.release()

    def _load_config(self) -> Configuration:
        try:
            return self._config_loader()
        except ConfigurationError as error:
            LOG.error("core.033", error_type=error_code(error))
            raise BackendFailure("broker configuration is unavailable") from error

    def _apply_rate_limit(self, caller_uid: int, interval: int) -> None:
        current = self._monotonic()
        with self._rate_lock:
            previous = self._last_request.get(caller_uid)
            if previous is not None and current - previous < interval:
                raise RateLimited("requests are being made too quickly")

    def _record_rate_limit(self, caller_uid: int) -> None:
        with self._rate_lock:
            self._last_request[caller_uid] = self._monotonic()

    def _load_request_preferences(self, target_uid: int) -> dict:
        if self._preferences is None:
            raise BackendFailure("preferences are unavailable")
        try:
            # Presentation changes cannot invalidate an in-flight approval.
            return {key: value for key, value in self._preferences.load(target_uid).items()
                    if key != "personal"}
        except (OSError, PreferencesError) as error:
            raise BackendFailure("preferences are unavailable") from error

    def _apply(self, target_uid: int,
               preferences: dict, desired_filter: tuple[bool, tuple[str, ...]],
               extension: tuple[int, int], correlation_id: str,
               termination_patterns: tuple[str, ...] | None = None) -> None:
        old_limit_type = old_daily_limit = old_filter = old_extension = None
        snapshot_complete = False
        termination_may_have_changed_processes = False
        try:
            # Capture every reversible value before the first write. A read
            # failure here has made no state change, so it needs public error
            # translation but must not attempt a partial rollback.
            old_limit_type = self._accounts.get_limit_type(target_uid)
            old_daily_limit = self._accounts.get_daily_limit(target_uid)
            old_filter = self._accounts.get_filter(target_uid)
            old_extension = self._accounts.get_extension(target_uid)
            snapshot_complete = True
            desired_daily_limit = preferences["daily_time_limit_minutes"] * 60
            if old_limit_type == 0 or old_daily_limit != desired_daily_limit:
                LOG.info("core.034", request=correlation_id)
                if old_daily_limit != desired_daily_limit:
                    self._accounts.set_daily_limit(target_uid, desired_daily_limit)
                    if self._accounts.get_daily_limit(target_uid) != desired_daily_limit:
                        raise BackendFailure("daily-limit verification failed")
                if old_limit_type == 0:
                    self._accounts.set_limit_type(target_uid, DAILY_LIMIT_FLAG)
                    if self._accounts.get_limit_type(target_uid) != DAILY_LIMIT_FLAG:
                        raise BackendFailure("limit-type verification failed")
            LOG.info("core.035", request=correlation_id)
            self._accounts.set_filter(target_uid, desired_filter)
            if self._accounts.get_filter(target_uid) != desired_filter:
                raise BackendFailure("app-filter verification failed")
            if termination_patterns is not None:
                LOG.info("core.036", request=correlation_id)
                termination_may_have_changed_processes = True
                terminated = self._running_apps.terminate(
                    target_uid, desired_filter[1], termination_patterns,
                )
                if type(terminated) is not int or terminated < 0:
                    raise BackendFailure("blocked application termination failed")
                termination_may_have_changed_processes = terminated > 0
                LOG.info("core.037", request=correlation_id, count=terminated)
            LOG.info("core.038", request=correlation_id)
            self._write_extension(target_uid, extension)
            if self._accounts.get_extension(target_uid) != extension:
                raise BackendFailure("extension verification failed")
            self._observe_grant(target_uid, *extension)
        except Exception as error:
            # Preserve the primary failure even if rollback raises a different
            # error with an explicit cause that hides the original context.
            record_exception(error)
            if not snapshot_complete:
                LOG.warning("core.039", request=correlation_id, error_type=error_code(error))
            elif termination_may_have_changed_processes:
                # A killed process cannot be restored. Keep the canonical
                # hard+soft block filter active, but restore every reversible
                # account value and never publish the requested time grant.
                self._restore_after_termination(
                    target_uid, old_limit_type, old_daily_limit, desired_filter,
                    old_extension, correlation_id,
                )
            else:
                self._restore(
                    target_uid, old_limit_type, old_daily_limit, old_filter,
                    old_extension, correlation_id,
                )
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("account update failed") from error

    def _restore_after_termination(
            self, target_uid: int, old_limit_type: int, old_daily_limit: int,
            desired_filter, old_extension, correlation_id: str) -> None:
        try:
            LOG.warning("core.040", request=correlation_id)
            self._write_extension(target_uid, old_extension)
            self._accounts.set_limit_type(target_uid, old_limit_type)
            self._accounts.set_daily_limit(target_uid, old_daily_limit)
            self._accounts.set_filter(target_uid, desired_filter)
            if (self._accounts.get_extension(target_uid) != old_extension or
                    self._accounts.get_filter(target_uid) != desired_filter or
                    self._accounts.get_limit_type(target_uid) != old_limit_type or
                    self._accounts.get_daily_limit(target_uid) != old_daily_limit):
                raise RuntimeError("post-termination rollback read-back mismatch")
        except Exception as error:
            LOG.critical("core.041", request=correlation_id)
            raise RollbackFailure(
                "account rollback after app termination could not be verified"
            ) from error

    def _restore(self, target_uid: int, old_limit_type: int, old_daily_limit: int,
                 old_filter, old_extension, correlation_id: str | None) -> None:
        try:
            if correlation_id is None:
                LOG.warning("core.parent-control-rollback")
            else:
                LOG.warning("core.042", request=correlation_id)
            self._write_extension(target_uid, old_extension)
            self._accounts.set_filter(target_uid, old_filter)
            self._accounts.set_limit_type(target_uid, old_limit_type)
            self._accounts.set_daily_limit(target_uid, old_daily_limit)
            if (self._accounts.get_extension(target_uid) != old_extension or
                    self._accounts.get_filter(target_uid) != old_filter or
                    self._accounts.get_limit_type(target_uid) != old_limit_type or
                    self._accounts.get_daily_limit(target_uid) != old_daily_limit):
                raise RuntimeError("rollback read-back mismatch")
        except Exception as error:
            if correlation_id is None:
                LOG.critical("core.parent-control-rollback-failed")
            else:
                LOG.critical("core.041", request=correlation_id)
            raise RollbackFailure("account rollback could not be verified") from error
