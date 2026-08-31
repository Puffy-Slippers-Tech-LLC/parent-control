"""Policy and transactional behavior independent of D-Bus bindings."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .config import Configuration, ConfigurationError, UINT32_MAX
from .preferences import PreferencesError, blocked_targets, validate_preferences

LOG = logging.getLogger("oh-no-parent-control")
MAX_LOCAL_MIDNIGHT_SECONDS = 26 * 60 * 60
MIN_REQUEST_SECONDS = 6
MAX_REQUEST_SECONDS = 24 * 60 * 60
MIN_MANAGED_UID = 1000
DAILY_LIMIT_FLAG = 1 << 1


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


class Authorizer(Protocol):
    def check(self, sender: str, correlation_id: str, target_label: str) -> str: ...


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


def seconds_until_local_midnight(now: datetime) -> int:
    if now.tzinfo is None:
        raise ValueError("approval time must be timezone-aware")
    tomorrow = now.date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)
    seconds = int(midnight.timestamp() - now.timestamp())
    if not 0 < seconds <= MAX_LOCAL_MIDNIGHT_SECONDS:
        raise BackendFailure("local-midnight duration is outside the safe range")
    return seconds


class Broker:
    def __init__(self, config_loader: Callable[[], Configuration], authorizer: Authorizer,
                 accounts: Accounts, preferences: Preferences | None = None,
                 extensions: Extensions | None = None, *, monotonic=time.monotonic,
                 now=lambda: datetime.now().astimezone(), caller_alive=lambda _sender: True):
        self._config_loader = config_loader
        self._authorizer = authorizer
        self._accounts = accounts
        self._preferences = preferences
        self._extensions = extensions
        self._monotonic = monotonic
        self._now = now
        self._caller_alive = caller_alive
        self._request_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._last_request = {}

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
        try:
            return self._preferences.save(target.uid, requested)
        except PreferencesError as error:
            raise BackendFailure("preferences could not be saved") from error

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

    def set_parent_control(self, caller_uid: int, target_uid: int, enabled: bool) -> dict:
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        if type(enabled) is not bool:
            raise InvalidRequest("enabled state must be boolean")
        target = self._target(config, target_uid)
        if self._preferences is None or self._extensions is None:
            raise BackendFailure("extension management is unavailable")
        try:
            current = self._preferences.load(target.uid)
            previous = current["parent_control_enabled"]
            self._extensions.set_enabled(target.uid, enabled)
            current["parent_control_enabled"] = enabled
            try:
                return self._preferences.save(target.uid, current)
            except Exception:
                self._extensions.set_enabled(target.uid, previous)
                raise
        except (OSError, RuntimeError, PreferencesError) as error:
            raise BackendFailure("could not change parent-control state") from error

    def request_access(self, caller_uid: int, sender: str, target_uid: int,
                       duration_seconds: int,
                       allow_soft_blocked_apps: bool) -> tuple[str, str]:
        correlation_id = str(uuid.uuid4())
        if not self._request_lock.acquire(blocking=False):
            raise Busy("another request is already in progress")
        try:
            config = self._load_config()
            self._check_caller(config, caller_uid)
            if type(duration_seconds) is not int or not (
                duration_seconds == 0 or
                MIN_REQUEST_SECONDS <= duration_seconds <= MAX_REQUEST_SECONDS
            ):
                raise InvalidRequest("duration is outside the supported range")
            if type(allow_soft_blocked_apps) is not bool:
                raise InvalidRequest("allow-soft value must be boolean")
            target = self._target(config, target_uid)
            self._apply_rate_limit(caller_uid, config.minimum_request_interval_seconds)
            LOG.info("request=%s caller_uid=%d target_uid=%d duration_seconds=%d "
                     "allow_soft=%s stage=authorize", correlation_id, caller_uid,
                     target.uid, duration_seconds, allow_soft_blocked_apps)

            outcome = self._authorizer.check(sender, correlation_id, target.label)
            if outcome not in {"approved", "denied", "cancelled"}:
                raise BackendFailure("authorizer returned an invalid outcome")
            if outcome != "approved":
                LOG.info("request=%s outcome=%s", correlation_id, outcome)
                return correlation_id, outcome
            if not self._caller_alive(sender):
                LOG.warning("request=%s outcome=denied reason=caller-disconnected", correlation_id)
                return correlation_id, "denied"
            # Fail closed if the selected account changed while the parent was
            # authenticating (including an AccountType promotion to admin).
            if self._target(config, target_uid) != target:
                raise AccessDenied("selected account changed during authorization")

            approved_at = self._now()
            duration = duration_seconds or seconds_until_local_midnight(approved_at)
            issued_at = int(approved_at.timestamp())
            if issued_at <= 0 or issued_at > (1 << 64) - 1 or not 0 < duration <= UINT32_MAX:
                raise BackendFailure("calculated extension is outside the supported range")
            self._apply(
                config, target.uid, allow_soft_blocked_apps,
                (issued_at, duration), correlation_id
            )
            LOG.info("request=%s outcome=approved", correlation_id)
            return correlation_id, "approved"
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

    def _apply(self, config: Configuration, target_uid: int,
               allow_soft_blocked_apps: bool,
               extension: tuple[int, int], correlation_id: str) -> None:
        old_limit_type = self._accounts.get_limit_type(target_uid)
        old_daily_limit = self._accounts.get_daily_limit(target_uid)
        old_filter = self._accounts.get_filter(target_uid)
        old_extension = self._accounts.get_extension(target_uid)
        if self._preferences is None:
            raise BackendFailure("preference store is unavailable")
        try:
            targets = blocked_targets(
                self._preferences.load(target_uid), allow_soft_blocked_apps,
            )
        except PreferencesError as error:
            raise BackendFailure("preferences are unavailable") from error
        desired_filter = (False, targets)
        try:
            if old_limit_type == 0 or old_daily_limit != 0:
                LOG.info("request=%s stage=limit-initialize", correlation_id)
                if old_daily_limit != 0:
                    self._accounts.set_daily_limit(target_uid, 0)
                    if self._accounts.get_daily_limit(target_uid) != 0:
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
