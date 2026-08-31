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

LOG = logging.getLogger("oh-no-parent-control")
MAX_LOCAL_MIDNIGHT_SECONDS = 26 * 60 * 60
MIN_REQUEST_SECONDS = 6
MAX_REQUEST_SECONDS = 24 * 60 * 60


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


class Authorizer(Protocol):
    def check(self, sender: str, correlation_id: str) -> str: ...


class Accounts(Protocol):
    def get_filter(self, child_uid: int) -> tuple[bool, tuple[str, ...]]: ...
    def set_filter(self, child_uid: int, value: tuple[bool, tuple[str, ...]]) -> None: ...
    def get_extension(self, child_uid: int) -> tuple[int, int]: ...
    def set_extension(self, child_uid: int, value: tuple[int, int]) -> None: ...


@dataclass(frozen=True)
class RequestOptions:
    child_label: str


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
                 accounts: Accounts, *, monotonic=time.monotonic,
                 now=lambda: datetime.now().astimezone(), caller_alive=lambda _sender: True):
        self._config_loader = config_loader
        self._authorizer = authorizer
        self._accounts = accounts
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

    def get_options(self, caller_uid: int) -> RequestOptions:
        config = self._load_config()
        self._check_caller(config, caller_uid)
        return RequestOptions(config.child_label)

    def request_access(self, caller_uid: int, sender: str, duration_seconds: int,
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
            self._apply_rate_limit(caller_uid, config.minimum_request_interval_seconds)
            LOG.info("request=%s caller_uid=%d child_uid=%d duration_seconds=%d "
                     "allow_soft=%s stage=authorize", correlation_id, caller_uid,
                     config.child_uid, duration_seconds, allow_soft_blocked_apps)

            outcome = self._authorizer.check(sender, correlation_id)
            if outcome not in {"approved", "denied", "cancelled"}:
                raise BackendFailure("authorizer returned an invalid outcome")
            if outcome != "approved":
                LOG.info("request=%s outcome=%s", correlation_id, outcome)
                return correlation_id, outcome
            if not self._caller_alive(sender):
                LOG.warning("request=%s outcome=denied reason=caller-disconnected", correlation_id)
                return correlation_id, "denied"

            approved_at = self._now()
            duration = duration_seconds or seconds_until_local_midnight(approved_at)
            issued_at = int(approved_at.timestamp())
            if issued_at <= 0 or issued_at > (1 << 64) - 1 or not 0 < duration <= UINT32_MAX:
                raise BackendFailure("calculated extension is outside the supported range")
            self._apply(
                config, allow_soft_blocked_apps, (issued_at, duration), correlation_id
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

    def _apply(self, config: Configuration, allow_soft_blocked_apps: bool,
               extension: tuple[int, int], correlation_id: str) -> None:
        child_uid = config.child_uid
        old_filter = self._accounts.get_filter(child_uid)
        targets = list(config.app_filter.hard_blocked_targets)
        if not allow_soft_blocked_apps:
            targets.extend(config.app_filter.soft_blocked_targets)
        desired_filter = (False, tuple(sorted(set(targets))))
        try:
            LOG.info("request=%s stage=filter-write", correlation_id)
            self._accounts.set_filter(child_uid, desired_filter)
            if self._accounts.get_filter(child_uid) != desired_filter:
                raise BackendFailure("app-filter verification failed")
        except Exception as error:
            self._restore_filter(child_uid, old_filter, correlation_id)
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("app-filter update failed") from error
        try:
            LOG.info("request=%s stage=extension-write", correlation_id)
            self._accounts.set_extension(child_uid, extension)
            if self._accounts.get_extension(child_uid) != extension:
                raise BackendFailure("extension verification failed")
        except Exception as error:
            self._restore_filter(child_uid, old_filter, correlation_id)
            if isinstance(error, BrokerError):
                raise
            raise BackendFailure("extension update failed") from error

    def _restore_filter(self, child_uid: int, old_filter, correlation_id: str) -> None:
        try:
            LOG.warning("request=%s stage=filter-rollback", correlation_id)
            self._accounts.set_filter(child_uid, old_filter)
            if self._accounts.get_filter(child_uid) != old_filter:
                raise RuntimeError("rollback read-back mismatch")
        except Exception as error:
            LOG.critical("request=%s outcome=rollback-failed", correlation_id)
            raise RollbackFailure("app-filter rollback could not be verified") from error
