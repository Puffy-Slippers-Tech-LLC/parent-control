"""Policy and transactional behavior independent of D-Bus bindings."""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .config import Configuration, ConfigurationError, UINT32_MAX
from .preferences import (
    MAX_DAILY_LIMIT_MINUTES, MIN_DAILY_LIMIT_MINUTES, PreferencesError,
    blocked_targets, validate_preferences,
)

LOG = logging.getLogger("oh-no-parent-control")
MAX_LOCAL_MIDNIGHT_SECONDS = 26 * 60 * 60
MIN_REQUEST_SECONDS = 6
MAX_REQUEST_SECONDS = 24 * 60 * 60
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


@dataclass(frozen=True)
class TimeStatus:
    daily_allowance_remaining_seconds: int
    one_time_grant_remaining_seconds: int
    additional_one_time_grant_seconds: int
    calculated_active_extension_seconds: int


class Authorizer(Protocol):
    def check(self, request_kind: str, sender: str, correlation_id: str, target_label: str,
              approver_username: str, requested_duration: str,
              allow_soft_blocked_apps: bool) -> str: ...


class Accounts(Protocol):
    def list_users(self) -> tuple[UserAccount, ...]: ...
    def get_user(self, uid: int) -> UserAccount: ...
    def get_filter(self, target_uid: int) -> tuple[bool, tuple[str, ...]]: ...
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
                       allow_soft: bool) -> dict: ...


class Extensions(Protocol):
    def set_enabled(self, uid: int, enabled: bool) -> None: ...


class TimerUsage(Protocol):
    def query_usage(self, uid: int) -> tuple[tuple[int, int], ...]: ...
    def query_usage_as(
            self, uid: int, approver: UserAccount) -> tuple[tuple[int, int], ...]: ...


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


def format_requested_duration(duration_seconds: int) -> str:
    """Return the kiosk-selected duration as concise human-readable text."""
    if duration_seconds == 0:
        return "the rest of the day"
    hours, remainder = divmod(duration_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    for value, singular in ((hours, "hour"), (minutes, "minute"), (seconds, "second")):
        if value:
            parts.append(f"{value} {singular}{'' if value == 1 else 's'}")
    return ", ".join(parts)


class Broker:
    def __init__(self, config_loader: Callable[[], Configuration], authorizer: Authorizer,
                 accounts: Accounts, preferences: Preferences | None = None,
                 extensions: Extensions | None = None, timer_usage: TimerUsage | None = None,
                 application_catalog: Callable[[UserAccount], tuple[dict, ...]] | None = None,
                 *, monotonic=time.monotonic,
                 now=lambda: datetime.now().astimezone(), caller_alive=lambda _sender: True):
        self._config_loader = config_loader
        self._authorizer = authorizer
        self._accounts = accounts
        self._preferences = preferences
        self._extensions = extensions
        self._timer_usage = timer_usage
        self._application_catalog = application_catalog
        self._monotonic = monotonic
        self._now = now
        self._caller_alive = caller_alive
        self._request_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._last_request = {}

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

    def get_time_status(self, caller_uid: int, target_uid: int,
                        additional_seconds: int = 0) -> TimeStatus:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot inspect time for this account")
        return self._time_status(target.uid, additional_seconds)

    def _time_status(self, target_uid: int, additional_seconds: int) -> TimeStatus:
        if self._preferences is None or self._timer_usage is None:
            raise BackendFailure("remaining-time status is unavailable")
        try:
            preferences = self._preferences.load(target_uid)
            usage_entries = self._timer_usage.query_usage(target_uid)
            grant_time, grant_duration = self._accounts.get_extension(target_uid)
        except Exception as error:
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
            return self._accounts.get_user(caller_uid).is_admin
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

    @staticmethod
    def _eligible_approver(config: Configuration, user: UserAccount) -> bool:
        return (
            MIN_MANAGED_UID <= user.uid <= UINT32_MAX and
            user.uid != config.kiosk_uid and
            user.is_local and not user.is_system and not user.is_locked and
            user.is_admin and
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
            return self._application_catalog(target)
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
            for desktop_id, policy in preferences["apps"].items():
                if desktop_id in current_targets:
                    policy["targets"] = current_targets[desktop_id]
            return validate_preferences(preferences)
        except Exception as error:
            raise BackendFailure("application catalog is unavailable") from error

    def set_preferences(self, caller_uid: int, target_uid: int, value: object) -> dict:
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
        preferences_saved = False
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
            return saved
        except Exception as error:
            try:
                if preferences_saved:
                    self._preferences.save(target.uid, current)
                self._accounts.set_filter(target.uid, old_filter)
                if self._accounts.get_filter(target.uid) != old_filter:
                    raise RuntimeError("app-filter rollback read-back mismatch")
            except Exception as rollback_error:
                raise RollbackFailure(
                    "app-filter rollback could not be verified"
                ) from rollback_error
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("app filter could not be applied") from error

    def update_request_preferences(self, caller_uid: int, target_uid: int,
                                   selected: str, custom: float,
                                   allow_soft: bool) -> dict:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot update this account")
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            return self._preferences.update_request(
                target.uid, selected, custom, allow_soft,
            )
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
        if self._preferences is None or self._extensions is None:
            raise BackendFailure("extension management is unavailable")
        try:
            current = self._preferences.load(target.uid)
            previous = current["parent_control_enabled"]
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
                desired_filter = (False, blocked_targets(current, False))

                if not enabled:
                    self._accounts.set_limit_type(target.uid, desired_limit_type)
                self._accounts.set_daily_limit(target.uid, desired_daily_limit)
                if extension_changed:
                    self._accounts.set_extension(target.uid, (0, 0))
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
                return self._preferences.save(target.uid, current)
            except Exception as error:
                rollback_error = None
                try:
                    self._restore(
                        target.uid, old_limit_type, old_daily_limit, old_filter,
                        old_extension, "parent-control",
                    )
                except Exception as caught:
                    rollback_error = caught
                try:
                    if extension_changed:
                        self._extensions.set_enabled(target.uid, previous)
                except Exception as caught:
                    rollback_error = rollback_error or caught
                if rollback_error is not None:
                    raise RollbackFailure(
                        "parent-control rollback could not be verified"
                    ) from rollback_error
                raise error
        except (OSError, RuntimeError, PreferencesError) as error:
            if isinstance(error, RollbackFailure):
                raise
            raise BackendFailure("could not change parent-control state") from error

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
        if not self._request_lock.acquire(blocking=False):
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
            if request_kind == "child" and not preferences["parent_control_enabled"]:
                raise AccessDenied("parent control is not enabled for this account")
            self._apply_rate_limit(caller_uid, config.minimum_request_interval_seconds)
            LOG.info("request=%s caller_uid=%d target_uid=%d approver_uid=%d "
                     "duration_seconds=%d allow_soft=%s kind=%s stage=authorize",
                     correlation_id, caller_uid, target.uid, approver.uid,
                     duration_seconds, allow_soft_blocked_apps, request_kind)

            outcome = self._authorizer.check(
                request_kind, sender, correlation_id, target.label, approver.username,
                format_requested_duration(duration_seconds),
                allow_soft_blocked_apps,
            )
            if outcome not in {"approved", "denied", "cancelled"}:
                raise BackendFailure("authorizer returned an invalid outcome")
            if outcome != "approved":
                LOG.info("request=%s outcome=%s", correlation_id, outcome)
                return correlation_id, outcome, 0
            if not self._caller_alive(sender):
                LOG.warning("request=%s outcome=denied reason=caller-disconnected", correlation_id)
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
            else:
                if self._preferences is None or self._timer_usage is None:
                    raise BackendFailure("remaining-time status is unavailable")
                LOG.info("request=%s stage=usage-query approver_uid=%d",
                         correlation_id, approver.uid)
                try:
                    usage_entries = self._timer_usage.query_usage_as(target.uid, approver)
                except Exception as error:
                    category = getattr(error, "category", type(error).__name__)
                    LOG.warning("request=%s stage=usage-query outcome=failed error=%s",
                                correlation_id, category)
                    raise BackendFailure("remaining-time status is unavailable") from error
                LOG.info("request=%s stage=usage-query outcome=accepted", correlation_id)

                # Fail closed before consuming a result obtained under an
                # identity which may have changed during the helper call.
                if not self._caller_alive(sender):
                    LOG.warning("request=%s outcome=denied reason=caller-disconnected",
                                correlation_id)
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
                duration = self._time_status_from_usage(
                    preferences, usage_entries, grant_time, grant_duration,
                    duration_seconds, issued_at_time,
                ).calculated_active_extension_seconds

            # The identity-scoped query may take up to the backend timeout.
            # Revalidate again immediately before privileged account writes.
            if not self._caller_alive(sender):
                LOG.warning("request=%s outcome=denied reason=caller-disconnected",
                            correlation_id)
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
            self._apply(
                target.uid, preferences, desired_filter,
                (issued_at, duration), correlation_id,
            )
            LOG.info("request=%s outcome=approved", correlation_id)
            return correlation_id, "approved", duration
        finally:
            self._request_lock.release()

    def _load_config(self) -> Configuration:
        try:
            return self._config_loader()
        except ConfigurationError as error:
            LOG.error("configuration rejected: %s", error)
            raise BackendFailure("broker configuration is unavailable") from error

    def _apply_rate_limit(self, caller_uid: int, interval: int) -> None:
        current = self._monotonic()
        with self._rate_lock:
            previous = self._last_request.get(caller_uid)
            if previous is not None and current - previous < interval:
                raise RateLimited("requests are being made too quickly")
            self._last_request[caller_uid] = current

    def _load_request_preferences(self, target_uid: int) -> dict:
        if self._preferences is None:
            raise BackendFailure("preferences are unavailable")
        try:
            return self._preferences.load(target_uid)
        except (OSError, PreferencesError) as error:
            raise BackendFailure("preferences are unavailable") from error

    def _apply(self, target_uid: int,
               preferences: dict, desired_filter: tuple[bool, tuple[str, ...]],
               extension: tuple[int, int], correlation_id: str) -> None:
        old_limit_type = self._accounts.get_limit_type(target_uid)
        old_daily_limit = self._accounts.get_daily_limit(target_uid)
        old_filter = self._accounts.get_filter(target_uid)
        old_extension = self._accounts.get_extension(target_uid)
        try:
            desired_daily_limit = preferences["daily_time_limit_minutes"] * 60
            if old_limit_type == 0 or old_daily_limit != desired_daily_limit:
                LOG.info("request=%s stage=limit-initialize", correlation_id)
                if old_daily_limit != desired_daily_limit:
                    self._accounts.set_daily_limit(target_uid, desired_daily_limit)
                    if self._accounts.get_daily_limit(target_uid) != desired_daily_limit:
                        raise BackendFailure("daily-limit verification failed")
                if old_limit_type == 0:
                    self._accounts.set_limit_type(target_uid, DAILY_LIMIT_FLAG)
                    if self._accounts.get_limit_type(target_uid) != DAILY_LIMIT_FLAG:
                        raise BackendFailure("limit-type verification failed")
            LOG.info("request=%s stage=filter-write", correlation_id)
            self._accounts.set_filter(target_uid, desired_filter)
            if self._accounts.get_filter(target_uid) != desired_filter:
                raise BackendFailure("app-filter verification failed")
            LOG.info("request=%s stage=extension-write", correlation_id)
            self._accounts.set_extension(target_uid, extension)
            if self._accounts.get_extension(target_uid) != extension:
                raise BackendFailure("extension verification failed")
        except Exception as error:
            self._restore(
                target_uid, old_limit_type, old_daily_limit, old_filter,
                old_extension, correlation_id,
            )
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("account update failed") from error

    def _restore(self, target_uid: int, old_limit_type: int, old_daily_limit: int,
                 old_filter, old_extension, correlation_id: str) -> None:
        try:
            LOG.warning("request=%s stage=rollback", correlation_id)
            self._accounts.set_extension(target_uid, old_extension)
            self._accounts.set_filter(target_uid, old_filter)
            self._accounts.set_limit_type(target_uid, old_limit_type)
            self._accounts.set_daily_limit(target_uid, old_daily_limit)
            if (self._accounts.get_extension(target_uid) != old_extension or
                    self._accounts.get_filter(target_uid) != old_filter or
                    self._accounts.get_limit_type(target_uid) != old_limit_type or
                    self._accounts.get_daily_limit(target_uid) != old_daily_limit):
                raise RuntimeError("rollback read-back mismatch")
        except Exception as error:
            LOG.critical("request=%s outcome=rollback-failed", correlation_id)
            raise RollbackFailure("account rollback could not be verified") from error
