"""Policy and transactional behavior independent of D-Bus bindings."""

from __future__ import annotations

from common.oh_no_parent_control_ui.diagnostic_events import (
    emit_failure_once, error_code, get_logger, operation, record_exception,
)
from common.oh_no_parent_control_ui.app_policy import replacement_policy_ids
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.localization import load_translations
from common.oh_no_parent_control_ui.approval_prompt import (
    format_approval_message, format_requested_duration,
)
from common.oh_no_parent_control_ui.languages import desktop_language_candidates
from common.oh_no_parent_control_ui.diagnostic_report import LANGUAGE_IDS, MAX_LANGUAGE_USERS
from .grant_diagnostics import GrantDiagnostics, buffer_saved_time_logs, log_pause_overrun, log_saved_time
from .execution_policy import ExecutionPolicyError
from .extension_manager import ChildExtensionFailed, ChildExtensionSessionLost, ChildExtensionUnavailable
import math
import re
import threading
import time
import uuid
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Callable, Iterable, Protocol
from zoneinfo import ZoneInfo

from .config import Configuration, ConfigurationError, UINT32_MAX
from .display_config import read_monitors_config
from .grant_store import (
    MAX_SAVED_SECONDS, UINT64_MAX, BridgeRepair, FixedGrant, GrantAccountError, GrantRecord,
    GrantStore, GrantStoreError, GrantTuple, PauseIntent, RedeemIntent, RedeemTimeState, SavedBalance,
    beyond_daily_seconds, merged_saved_seconds, new_grant_is_fixed, remaining_seconds, running_mode,
)
from .whats_new import WhatsNewCatalog, WhatsNewError
from .preferences import (
    MAX_DAILY_LIMIT_MINUTES, MIN_DAILY_LIMIT_MINUTES, PreferencesError, StoredPreferencesError,
    blocked_patterns, blocked_targets, validate_preferences, validate_language, validate_notifications,
    validate_time_grant_presets, MIN_TIME_GRANT_SECONDS, MAX_TIME_GRANT_SECONDS,
)

LOG = get_logger("core")
_NO_ACKNOWLEDGEMENT = object()
MAX_LOCAL_MIDNIGHT_SECONDS = 26 * 60 * 60
MIN_REQUEST_SECONDS = MIN_TIME_GRANT_SECONDS
MAX_REQUEST_SECONDS = MAX_TIME_GRANT_SECONDS
MIN_MANAGED_UID = 1000
DAILY_SCHEDULE_FLAG = 1 << 0
DAILY_LIMIT_FLAG = 1 << 1
FULL_DAY_SCHEDULE = (0, 86400)
# D-Bus uint64 values used by GJS must remain exactly representable in Number.
MAX_SAFE_DEADLINE_USEC = (1 << 53) - 1
CLOCK_SAMPLE_TOLERANCE_USEC = 1000
EXTENSION_RECOVERY_LOCK_TIMEOUT_SECONDS = 30
SESSION_LOCK_TIMEOUT_SECONDS = 5
SESSION_LOCK_POLL_SECONDS = 0.05
TRANSFER_MARGIN_SECONDS = 5
PAUSE_SESSION_ENTRY_TIMEOUT_SECONDS = SESSION_LOCK_TIMEOUT_SECONDS + 2 * TRANSFER_MARGIN_SECONDS
GRAPHICAL_SESSION_TYPES = frozenset({"wayland", "x11"})
APPROVER_USERNAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*[$]?$")
UsageIntervals = tuple[tuple[int, int], ...]


class BrokerError(RuntimeError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.Failed"


class InvalidRequest(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.InvalidRequest"


class AccessDenied(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.AccessDenied"


class Busy(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.Busy"


class DesktopInUse(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.DesktopInUse"


class Stale(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.Stale"


class _NoPausableTime(Stale):
    """The running fixed grant contributes no time that can be transferred."""


class RecoveryPending(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.RecoveryPending"


class BackendFailure(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.BackendFailure"

    def __init__(self, *args, expected=False):
        super().__init__(*args)
        self.expected = expected  # Preserve normal retry/refusal replies on D-Bus.


class RollbackFailure(BrokerError):
    dbus_name = "com.puffyslippers.OhNoParentControl1.Error.RollbackFailure"


class NativeDeadlineSuspended(RuntimeError):
    """The child session reports that native time is suspended."""


class AccountMissing(LookupError):
    """AccountsService confirmed that a UID no longer exists."""


class GrantAccountChanged(AccessDenied):
    """The adapter confirmed an identity or eligibility change at a bound write."""


class _GrantAccountInvalidated(AccessDenied):
    """The previous account's transaction must stop without retry or rollback."""


def emit_backend_failure(error: BrokerError, *, original=None) -> None:
    if (isinstance(error, RollbackFailure) or
            (isinstance(error, BackendFailure) and not error.expected)):
        emit_failure_once("broker", "backend", error, original=original)


@contextmanager
def _report_grant_recovery(stage):
    try:
        yield
    except (RecoveryPending, RollbackFailure):
        log_saved_time("grant.recovery", stage=stage, outcome="pending")
        raise
    except Exception:
        log_saved_time("grant.recovery", stage=stage, outcome="failed")
        raise


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


@dataclass(frozen=True)
class GrantStatus:
    revision: int
    evaluated_at_epoch_seconds: int
    daily_remaining_seconds: int
    running_remaining_seconds: int
    running_beyond_daily_seconds: int
    saved_seconds: int
    usable_seconds: int
    total_seconds: int
    running_mode: str
    running_end_epoch_seconds: int
    immediate_estimate_seconds: int
    deferred_estimate_seconds: int


@dataclass(frozen=True)
class SessionState:
    path: str
    session_id: str
    uid: int
    remote: bool
    active: bool
    locked: bool
    state: str
    kind: str
    started_monotonic: int


@dataclass(frozen=True)
class SavedTimeContext:
    caller_uid: int
    sender: str
    request_kind: str
    target: UserAccount
    preferences: dict
    session: SessionState
    lock_capture_complete: bool = False


@dataclass(frozen=True)
class DeferredApproval:
    correlation_id: str
    result_code: str
    pause_error: str = ""
    saved_seconds: int | None = None


@dataclass(frozen=True)
class DailyCapture:
    context: SavedTimeContext
    evaluated_at: datetime
    daily_remaining_seconds: int
    transfer_anchor: tuple[datetime, float]


@dataclass(frozen=True)
class _ActivePause:
    uid: int
    released: threading.Event = field(default_factory=threading.Event)
    waiter: threading.Lock = field(default_factory=threading.Lock)


@dataclass(eq=False)
class _GrantObservation:
    first_revision: int
    last_revision: int


@dataclass
class _RedeemAttempt:
    record: GrantRecord
    intent: RedeemIntent
    external: GrantTuple | None = None
    termination_may_have_changed_processes: bool = False
    original_filter: tuple[bool, tuple[str, ...]] | None = None


class Approval(Protocol):
    outcome: str

    def admit(self) -> bool: ...


class DeferredAuthorization(Approval, Protocol):
    session: SessionState | None

    def authenticate(self, target_label: str, approver_username: str, message: str) -> str: ...
    def admit(self, *, validate: Callable[[], None] | None = None) -> bool: ...


class Authorizer(Protocol):
    def check(self, request_kind: str, sender: str, correlation_id: str, target_label: str,
              approver_username: str, message: str) -> AbstractContextManager[Approval]: ...
    def watch_deferred(self, request_kind: str, sender: str, correlation_id: str,
                       caller_uid: int) -> AbstractContextManager[DeferredAuthorization]: ...


class Accounts(Protocol):
    def list_users(self) -> tuple[UserAccount, ...]: ...
    def diagnostic_user_roles(self, *, excluded_uid: int, deadline: float,
                              limit: int) -> tuple[str, list[tuple[int, str]]]: ...
    def get_user(self, uid: int) -> UserAccount: ...
    def bind_grant_mutations(self, uid: int, username: str) -> AbstractContextManager[None]: ...
    def get_filter(self, target_uid: int) -> tuple[bool, tuple[str, ...]]: ...
    def validate_filter(self, target_uid: int, value: tuple[bool, tuple[str, ...]]) -> None: ...
    def set_filter(self, target_uid: int, value: tuple[bool, tuple[str, ...]]) -> None: ...
    def get_extension(self, target_uid: int, *, deadline: float | None = None) -> GrantTuple: ...
    def set_extension(self, target_uid: int, value: GrantTuple, *,
                      deadline: float | None = None, wall_deadline: float | None = None) -> None: ...
    def get_limit_type(self, target_uid: int) -> int: ...
    def set_limit_type(self, target_uid: int, value: int) -> None: ...
    def get_daily_limit(self, target_uid: int) -> int: ...
    def set_daily_limit(self, target_uid: int, value: int) -> None: ...
    def get_daily_schedule(self, target_uid: int) -> tuple[int, int]: ...
    def set_daily_schedule(self, target_uid: int, value: tuple[int, int]) -> None: ...


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
                    recover_global_switch: bool = False) -> Callable[[], None] | None: ...


class TimerUsage(Protocol):
    def query_usage(self, uid: int, *,
                    timeout_seconds: float | None = None) -> UsageIntervals: ...
    def query_usage_as(
            self, uid: int, approver: UserAccount) -> UsageIntervals: ...
    def query_native_deadline(self, uid: int) -> int: ...


class Sessions(Protocol):
    def resolve(self, sender: str, *,
                timeout_seconds: float = SESSION_LOCK_TIMEOUT_SECONDS) -> SessionState | None: ...
    def get(self, path: str, *, timeout_seconds: float) -> SessionState: ...
    def for_user(self, uid: int, *, timeout_seconds: float) -> tuple[SessionState, ...]: ...
    def lock(self, session_id: str, *, timeout_seconds: float) -> None: ...


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


def local_now() -> datetime:
    """Read the system timezone's transition rules, including tomorrow's offset.

    Reopen the OS timezone file so a timezone change takes effect without a
    broker restart. astimezone() without a zone would retain only today's offset.
    """
    try:
        with open("/etc/localtime", "rb") as source:
            zone = ZoneInfo.from_file(source)
        return datetime.now(zone)
    except (OSError, ValueError) as error:
        raise BackendFailure("local timezone is unavailable") from error


def seconds_until_local_midnight(now: datetime) -> int:
    if now.tzinfo is None:
        raise ValueError("approval time must be timezone-aware")
    tomorrow = now.date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)
    seconds = int(midnight.timestamp() - now.timestamp())
    if not 0 < seconds <= MAX_LOCAL_MIDNIGHT_SECONDS:
        raise BackendFailure("local-midnight duration is outside the safe range")
    return seconds


def _valid_usage_interval(start: int, end: int) -> bool:
    return type(start) is int and type(end) is int and 0 <= start <= end


def _merge_usage_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        elif end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end)
    return merged


def _same_session(left: SessionState, right: SessionState) -> bool:
    return (left.path, left.session_id, left.uid, left.started_monotonic) == (
        right.path, right.session_id, right.uid, right.started_monotonic,
    )


class Broker:
    def __init__(self, config_loader: Callable[[], Configuration], authorizer: Authorizer,
                 accounts: Accounts, preferences: Preferences | None = None,
                 extensions: Extensions | None = None, timer_usage: TimerUsage | None = None,
                 application_catalog: Callable[[UserAccount], tuple[dict, ...]] | None = None,
                 running_apps: RunningApps | None = None,
                 *, monotonic=time.monotonic,
                 now=local_now, caller_alive=lambda _sender: True,
                 whats_new_loader=WhatsNewCatalog.load,
                 grant_store: GrantStore | None = None,
                 sessions: Sessions | None = None, sleep=time.sleep,
                 monitors_reader: Callable[[int], str] = read_monitors_config):
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
        self._grant_store = grant_store
        self._sessions = sessions
        self._sleep = sleep
        self._monitors_reader = monitors_reader
        self._request_lock = threading.Lock()
        self._grant_fence_lock = threading.Lock()
        self._grant_fences: dict[int, tuple[int, int]] = {}
        self._grant_observations: dict[int, set[_GrantObservation]] = {}
        self._grant_publications = 0
        self._request_lock_diagnostic = None
        self._active_pause: _ActivePause | None = None
        self._transaction_revision = 0
        self._grant_diagnostics = GrantDiagnostics()

    def _acquire_request_lock(self, diagnostic_kind="other", *, timeout=0):
        if not self._request_lock.acquire(timeout=timeout):
            try:
                owner = self._request_lock_diagnostic
                LOG.info("core.transaction-busy", requested=diagnostic_kind,
                         holder=owner[0] if owner else "other",
                         elapsed_ms=min(2147483647, max(0, int((time.monotonic() - owner[1]) * 1000))) if owner else 0,
                         holder_known=owner is not None)
            except Exception:
                pass
            return False
        self._transaction_revision += 1
        try:
            self._request_lock_diagnostic = (diagnostic_kind, time.monotonic())
        except Exception:
            self._request_lock_diagnostic = None
        return True

    def _release_request_lock(self):
        # Clear before unlocking; a new owner must never inherit old metadata.
        # This advisory snapshot does not authorize or synchronize any work.
        self._request_lock_diagnostic = None
        pause = self._active_pause
        self._active_pause = None
        self._request_lock.release()
        if pause is not None:
            pause.released.set()

    def _extension_window_elapsed(self, deadline, wall_deadline):
        return ((deadline is not None and self._monotonic() >= deadline) or
                (wall_deadline is not None and self._now().timestamp() >= wall_deadline))

    def _write_extension(self, uid, value, *, deadline=None, wall_deadline=None, readback=None):
        if self._extension_window_elapsed(deadline, wall_deadline):
            raise TimeoutError("extension write window elapsed")
        self._grant_diagnostics.write_started(uid)
        bounds = {} if deadline is None else {"deadline": deadline}
        wall_bound = {} if wall_deadline is None else {"wall_deadline": wall_deadline}
        stage = "extension-write"
        try:
            self._accounts.set_extension(uid, value, **bounds, **wall_bound)
            if self._extension_window_elapsed(deadline, wall_deadline):
                raise TimeoutError("extension write window elapsed")
            stage = "extension-readback"
            live = self._accounts.get_extension(uid, **bounds) if readback is None else readback()
            if live != value:
                raise BackendFailure("extension verification failed")
            if self._extension_window_elapsed(deadline, wall_deadline):
                raise TimeoutError("extension verification window elapsed")
        except Exception:
            if deadline is not None:
                log_pause_overrun(self._monotonic, deadline, stage)
            raise
        try:
            self._grant_diagnostics.wrote(uid, value)
            self._observe_grant(uid, *value)
        except Exception:
            get_logger("grant").warning("grant.invalid")

    def _prepare_time_state(self, uid, limit_type, daily_limit, *, check_account=lambda: None):
        # Malcontent 0.14 checks extensions even when LimitType is zero, then
        # asserts that a current extension has enabled limits. Clearing a grant
        # under an exhausted daily limit instead emits a lockable zero estimate.
        # A full-day, schedule-only bridge avoids both intermediate states. Its
        # local wall-clock range stays usable on 25-hour days too; a maximum
        # daily allowance does not. Keep the original schedule until finalization.
        if self._accounts.get_limit_type(uid) != 0 or limit_type != 0:
            check_account()
            self._accounts.set_daily_schedule(uid, FULL_DAY_SCHEDULE)
            if self._accounts.get_daily_schedule(uid) != FULL_DAY_SCHEDULE:
                raise BackendFailure("daily-schedule verification failed")
            check_account()
            self._accounts.set_limit_type(uid, DAILY_SCHEDULE_FLAG)
            if self._accounts.get_limit_type(uid) != DAILY_SCHEDULE_FLAG:
                raise BackendFailure("limit-type verification failed")
        check_account()
        self._accounts.set_daily_limit(uid, daily_limit)
        if self._accounts.get_daily_limit(uid) != daily_limit:
            raise BackendFailure("daily-limit verification failed")

    def _finish_time_state(self, uid, limit_type, daily_schedule, extension):
        self._write_extension(uid, extension)
        self._finalize_time_state(uid, limit_type, daily_schedule)

    def _finalize_time_state(self, uid, limit_type, daily_schedule, *, check_account=lambda: None):
        check_account()
        self._accounts.set_limit_type(uid, limit_type)
        if self._accounts.get_limit_type(uid) != limit_type:
            raise BackendFailure("limit-type verification failed")
        check_account()
        self._accounts.set_daily_schedule(uid, daily_schedule)
        if self._accounts.get_daily_schedule(uid) != daily_schedule:
            raise BackendFailure("daily-schedule verification failed")

    def _write_time_state(self, uid, limit_type, daily_limit, daily_schedule, extension):
        self._prepare_time_state(uid, limit_type, daily_limit)
        self._finish_time_state(uid, limit_type, daily_schedule, extension)

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
        users = [user for user in self._accounts.list_users() if self._eligible(config, user)]
        states, references = {}, {}
        for user in users:
            with operation() as reference:
                references[user.uid] = reference
                try:
                    states[user.uid] = "on" if self._preferences.load(user.uid)["parent_control_enabled"] else "off"
                except Exception as error:
                    states[user.uid] = "unknown"
                    record_exception(error)
        from .dependency_diagnostics import collect_gnome_shell_diagnostics
        try:
            collect_gnome_shell_diagnostics((user.uid for user in users), operation_ids=references)
        except Exception:
            get_logger("extension-manager").warning("extension-manager.shell-history", outcome="unavailable", count=0)
        self._extensions.collect_diagnostics((user.uid for user in users), saved_states=states,
                                             operation_ids=references)

    def refresh_enabled_extensions(self) -> tuple[int, ...]:
        """Reassert enabled children; retry unavailable child integrations at startup."""
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
            with operation():
                try:
                    preferences = self._preferences.load(user.uid)
                    if preferences["parent_control_enabled"]:
                        LOG.info("core.extension-startup", outcome="started")
                        try:
                            self._extensions.set_enabled(user.uid, True, recover_global_switch=True)
                        except (ChildExtensionUnavailable, ChildExtensionFailed) as error:
                            if isinstance(error, ChildExtensionFailed):
                                emit_failure_once("broker", "operation", error)
                            LOG.warning("core.extension-startup", outcome="child-unavailable")
                            LOG.error("core.001", error_type=error_code(error.__cause__ or error))
                            record_exception(error)
                            continue
                        refreshed.append(user.uid)
                        LOG.info("core.extension-startup", outcome="accepted")
                    else:
                        LOG.info("core.extension-startup", outcome="saved-off")
                except Exception as error:
                    LOG.error("core.extension-startup", outcome="failed")
                    LOG.error("core.001", error_type=error_code(error))
                    failure = BackendFailure("could not refresh the child extension")
                    emit_backend_failure(failure, original=error)
                    raise failure from error
        return tuple(refreshed)

    def extension_watch_uids(self) -> tuple[int, ...]:
        """Discover child sessions; this snapshot never authorizes a later write."""
        config = self._load_config()
        return tuple(user.uid for user in self._accounts.list_users()
                     if self._eligible(config, user))

    def reconcile_enabled_child(self, target_uid, action, *, expected_revision=None):
        """Revalidate a session hint under the same lock as parent policy writes."""
        if not self._acquire_request_lock("extension-monitor"):
            raise Busy("another request is already in progress")
        try:
            # This acquisition advances the revision once. Any other advance
            # since the unlocked observation makes its state stale.
            if (expected_revision is not None and
                    self._transaction_revision != expected_revision + 1):
                raise Busy("child extension observation is stale")
            config = self._load_config()
            target = self._accounts.get_user(target_uid)
            if not self._eligible(config, target):
                return False
            if not self._load_request_preferences(target.uid)["parent_control_enabled"]:
                return False
            action()
            return True
        finally:
            self._release_request_lock()

    def extension_reconciliation_revision(self):
        """Read before checking busy, then validate after the unlocked probe."""
        return self._transaction_revision

    def extension_reconciliation_busy(self):
        """A scheduling hint only; reconciliation still acquires/revalidates."""
        return self._request_lock.locked()

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
        try:
            grant_remaining = remaining_seconds(
                (grant_time, grant_duration), int(self._now().timestamp()),
            )
        except ValueError as error:
            raise BackendFailure("remaining-time grant is invalid") from error
        return calculate_active_extension_seconds(
            daily_allowance_remaining_seconds, grant_remaining, 0,
        )

    def calculate_own_deadline(self, caller_uid: int,
                               native_deadline_realtime_usec: int,
                               timer_deadline_realtime_usec: int) -> int:
        """Select the native/fallback endpoint and live grant; never renew time.

        Inputs are absolute CLOCK_REALTIME microseconds (zero means absent),
        output is absolute CLOCK_MONOTONIC microseconds. Observations retain the
        same child-supplied trust as CalculateOwnRemainingTime.
        """
        target = self._target(self._load_config(), caller_uid)
        endpoints = (native_deadline_realtime_usec, timer_deadline_realtime_usec)
        if any(type(value) is not int or not 0 <= value <= MAX_SAFE_DEADLINE_USEC
               for value in endpoints):
            raise InvalidRequest("deadline values must be safe unsigned microseconds")

        before = self._deadline_clock_sample()
        try:
            issued, duration = self._accounts.get_extension(target.uid)
        except Exception as error:
            raise BackendFailure("remaining-time grant is unavailable") from error
        if (type(issued) is not int or type(duration) is not int or
                issued < 0 or not 0 <= duration <= UINT32_MAX):
            raise BackendFailure("remaining-time grant is invalid")
        after = self._deadline_clock_sample()
        # Each real-time reading is bracketed by monotonic readings. The two
        # offset intervals must overlap within 1ms of clock/sample granularity.
        # A clock jump or suspend across the read needs a fresh calculation.
        lower = max(before[0] - before[1], after[0] - after[1])
        upper = min(before[2] - before[1], after[2] - after[1])
        if after[0] < before[2] or lower > upper + CLOCK_SAMPLE_TOLERANCE_USEC:
            raise BackendFailure("deadline clock mapping changed", expected=True)
        if any(value - after[1] > UINT32_MAX * 1_000_000 for value in endpoints):
            raise InvalidRequest("deadline is outside the remaining-time range")

        # A positive native endpoint remains binding even after it expires.
        allowance = native_deadline_realtime_usec or timer_deadline_realtime_usec
        grant = (issued + duration) * 1_000_000 if duration else 0
        if grant - after[1] > UINT32_MAX * 1_000_000:
            raise BackendFailure("remaining-time grant is invalid")
        # Use the earlier proven offset, consuming sampling and transport time.
        offset = min(before[0] - before[1], after[0] - after[1])
        deadline = max(0, max(allowance, grant) + offset)
        if deadline > MAX_SAFE_DEADLINE_USEC:
            raise BackendFailure("calculated deadline is invalid")
        return deadline

    def _deadline_clock_sample(self) -> tuple[int, int, int]:
        start = self._monotonic()
        realtime = self._now().timestamp()
        end = self._monotonic()
        if (not all(math.isfinite(value) and value >= 0
                    for value in (start, realtime, end)) or end < start):
            raise BackendFailure("deadline clocks are unavailable")
        # A descheduled sample cannot locate realtime closely enough to use
        # its conservative offset without expiring valid time prematurely.
        if (end - start) * 1_000_000 > CLOCK_SAMPLE_TOLERANCE_USEC:
            raise BackendFailure("deadline clock sample is uncertain", expected=True)
        return (math.floor(start * 1_000_000), round(realtime * 1_000_000),
                math.floor(end * 1_000_000))

    def prepare_own_session(self, caller_uid: int) -> bool:
        """Restore expired-grant app policy when a child resumes its session.

        A parent may renew an expired grant while the child is at the lock
        screen. Serialize with approval and re-read ActiveExtension under the
        transaction lock so a current grant always wins and its applications
        remain untouched.
        """
        if not self._acquire_request_lock("session-prepare"):
            if (not self._wait_for_active_pause(caller_uid) or
                    not self._acquire_request_lock("session-prepare")):
                raise Busy("another request is already in progress")
        try:
            config = self._load_config()
            target = self._grant_mutation_target(config, caller_uid)
            record = self._recover_grant_record_locked(target)
            grant = self._read_live_grant(target.uid)
            grant_time, grant_duration = grant

            now_seconds = int(self._now().timestamp())
            if grant_duration == 0:
                LOG.info("core.002")
                return False
            paused = (record is not None and record.fixed is not None and
                      record.fixed.ended_by_pause and record.fixed.grant == grant)
            if grant_time + grant_duration > now_seconds and not paused:
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
                public_error = error if isinstance(error, BrokerError) else BackendFailure(
                    "session application policy could not be prepared")
                emit_backend_failure(public_error, original=error)
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
                        failure = RollbackFailure("session app-filter rollback could not be verified")
                        emit_backend_failure(failure, original=rollback_error)
                        LOG.critical("core.007", error_type=error_code(rollback_error))
                        raise failure from rollback_error
                LOG.warning(
                    "core.008",
                    error_type=error_code(error),
                    strict_filter=termination_started,
                )
                if public_error is error:
                    raise
                raise public_error from error
        finally:
            self._release_request_lock()

    def _wait_for_active_pause(self, caller_uid: int) -> bool:
        # Keep one session-entry worker for the same child across pause
        # recovery, including unlocks that exhaust the client's Busy retries.
        pause = self._active_pause
        if pause is None or pause.uid != caller_uid or not pause.waiter.acquire(blocking=False):
            return False
        try:
            return pause.released.wait(PAUSE_SESSION_ENTRY_TIMEOUT_SECONDS)
        finally:
            pause.waiter.release()

    def recover_child_extension(self, caller_uid: int, target_uid: int, *,
                                on_recovered: Callable[[int], None] | None = None) -> bool:
        """Reassert saved enforcement for PAM and administrator management."""
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        # This runs in a D-Bus worker, so wait for the current transaction
        # instead of rejecting a valid login when background monitoring wins
        # the lock. Reload target and policy only after admission below.
        if not self._acquire_request_lock("extension-recovery",
                timeout=EXTENSION_RECOVERY_LOCK_TIMEOUT_SECONDS):
            raise Busy("another request is already in progress")
        try:
            for retry in (False, True):
                if not self._is_admin(caller_uid):
                    raise AccessDenied("administrator access is required")
                target = self._target(self._load_config(), target_uid)
                preferences = self._load_request_preferences(target.uid)
                if not preferences["parent_control_enabled"]:
                    return False
                if self._extensions is None:
                    raise BackendFailure("extension management is unavailable")
                try:
                    self._extensions.set_enabled(target.uid, True, recover_global_switch=True)
                except Exception as error:
                    session_lost = isinstance(error, ChildExtensionSessionLost)
                    # Fresh login can overlap logout. After session loss, activation
                    # has made no writes or verified their rollback, so retry once.
                    if session_lost and not retry:
                        continue
                    failure = BackendFailure("could not recover the child extension", expected=session_lost)
                    emit_backend_failure(failure, original=error)
                    raise failure from error
                if on_recovered is not None:
                    on_recovered(target.uid)
                return True
        finally:
            self._release_request_lock()

    def get_time_status(self, caller_uid: int, target_uid: int,
                        additional_seconds: int = 0) -> TimeStatus:
        config = self._load_config()
        target = self._target(config, target_uid)
        if caller_uid != target.uid and not self._can_manage_or_kiosk(config, caller_uid):
            raise AccessDenied("caller cannot inspect time for this account")
        return self._time_status(target.uid, additional_seconds,
                                 own=caller_uid == target.uid)

    def get_grant_status(
            self, caller_uid: int, target_uid: int, requested_seconds: int = 0, *,
            schedule_recovery: Callable[[int], None],
    ) -> GrantStatus:
        config = self._load_config()
        own = caller_uid == target_uid
        if not (own or caller_uid == config.kiosk_uid or
                self._is_admin(caller_uid, unavailable_is_backend_failure=True)):
            raise AccessDenied("caller cannot inspect time for this account")
        self._validate_approval_values(requested_seconds, False)
        transaction_revision = self._transaction_revision

        def check_transaction():
            if (self._request_lock.locked() or
                    self._transaction_revision != transaction_revision):
                raise Busy("another request is already in progress")

        target, record = self._read_grant_record_for_status(
            config, target_uid, schedule_recovery=schedule_recovery,
        )
        check_transaction()
        if self._preferences is None or self._timer_usage is None:
            raise BackendFailure("remaining-time status is unavailable")
        try:
            preferences = self._preferences.load(target.uid)
            usage = self._timer_usage.query_usage(target.uid)
            native_deadline = self._native_deadline(target.uid, preferences) if own else None
            live = self._read_live_grant(target.uid)
            now = self._now()
            evaluated_monotonic = self._monotonic() if native_deadline is not None else None
        except NativeDeadlineSuspended as error:
            raise Busy("native time is suspended while the child session is inactive") from error
        except BrokerError:
            raise
        except Exception as error:
            raise BackendFailure("remaining-time status is unavailable") from error
        check_transaction()
        try:
            evaluated_at = int(now.timestamp())
            if not 0 <= evaluated_at <= UINT64_MAX:
                raise ValueError("evaluation time is outside the supported range")
            daily = self._daily_remaining_from_usage(
                preferences, usage, now, evaluated_at, native_deadline,
                evaluated_monotonic=evaluated_monotonic,
            )
            running = remaining_seconds(live, evaluated_at) if live[1] else 0
            mode = running_mode(record, live, running)
            if mode == "none":
                running = 0
            running_end = sum(live) if running else 0
            beyond_daily = beyond_daily_seconds(daily, running)
            saved = record.saved.seconds if record.saved else 0
            usable = max(daily, running)
            total = usable + saved
            if total > UINT32_MAX or running_end > UINT64_MAX:
                raise ValueError("grant status is outside the supported range")
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
            raise BackendFailure("remaining-time status is invalid") from error

        immediate = deferred = 0
        if requested_seconds:
            if usable + requested_seconds <= UINT32_MAX:
                immediate = usable + requested_seconds
            saved_with_request = saved + requested_seconds
            if saved_with_request <= MAX_SAVED_SECONDS:
                # The store-only approval can succeed even if pausing would exceed the limit.
                deferred = saved_with_request
                if mode == "fixed" and deferred + beyond_daily <= MAX_SAVED_SECONDS:
                    deferred += beyond_daily
        current_target, _ = self._read_grant_record_for_status(
            config, target_uid, schedule_recovery=schedule_recovery,
            expected_revision=record.revision,
        )
        if current_target.username != target.username:
            raise Busy("selected account changed during the status read")
        check_transaction()
        return GrantStatus(
            record.revision, evaluated_at, daily, running, beyond_daily, saved, usable, total,
            mode, running_end, immediate, deferred,
        )

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

    def _time_status(self, target_uid: int, additional_seconds: int,
                     *, own: bool = False) -> TimeStatus:
        if self._preferences is None or self._timer_usage is None:
            raise BackendFailure("remaining-time status is unavailable")
        stage = "preferences"
        try:
            preferences = self._preferences.load(target_uid)
            stage = "usage"
            usage_entries = self._timer_usage.query_usage(target_uid)
            native_deadline = self._native_deadline(target_uid, preferences) if own else None
            stage = "grant"
            grant_time, grant_duration = self._accounts.get_extension(target_uid)
        except NativeDeadlineSuspended as error:
            raise Busy("native time is suspended while the child session is inactive") from error
        except Exception as error:
            LOG.warning("core.009", stage=stage, error_type=error_code(error))
            raise BackendFailure("remaining-time status is unavailable") from error

        return self._time_status_from_usage(
            preferences, usage_entries, grant_time, grant_duration, additional_seconds,
            native_deadline=native_deadline,
        )

    def _native_deadline(self, target_uid: int, preferences: dict) -> int | None:
        if not (preferences["parent_control_enabled"] and
                preferences["daily_time_limit_minutes"] > 0):
            return None
        deadline = self._timer_usage.query_native_deadline(target_uid)
        if type(deadline) is not int or not 0 <= deadline <= (1 << 64) - 1:
            raise BackendFailure("native remaining time is invalid")
        return deadline

    def _time_status_from_usage(
            self, preferences: dict, usage_entries: UsageIntervals,
            grant_time: int, grant_duration: int, additional_seconds: int,
            evaluated_at: datetime | None = None,
            *, native_deadline: int | None = None) -> TimeStatus:
        now = evaluated_at or self._now()
        now_seconds = int(now.timestamp())
        daily_remaining = self._daily_remaining_from_usage(
            preferences, usage_entries, now, now_seconds, native_deadline,
        )
        try:
            grant_remaining = remaining_seconds((grant_time, grant_duration), now_seconds)
        except ValueError as error:
            raise InvalidRequest("remaining-time values must be unsigned 32-bit integers") from error
        calculated = calculate_active_extension_seconds(
            daily_remaining, grant_remaining, additional_seconds,
        )
        return TimeStatus(
            daily_remaining, grant_remaining, additional_seconds, calculated,
        )

    def _daily_remaining_from_usage(
            self, preferences: dict, usage_entries: UsageIntervals, now: datetime,
            now_seconds: int, native_deadline: int | None, *,
            evaluated_monotonic: float | None = None,
    ) -> int:
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
            if not _valid_usage_interval(start, end):
                raise BackendFailure("timer usage returned an invalid interval")
            clipped_start = max(start, start_of_today_seconds)
            clipped_end = min(end, now_seconds)
            if clipped_end > clipped_start:
                today_intervals.append((clipped_start, clipped_end))
        used_today = sum(end - start for start, end in _merge_usage_intervals(today_intervals))
        daily_remaining = max(0, daily_limit_seconds - used_today)
        if native_deadline is not None:
            # Completed records omit uninterrupted activity. The child's fresh
            # native deadline may only reduce that operand; the live grant and
            # authenticated additional interval remain broker-owned.
            if evaluated_monotonic is None:
                evaluated_monotonic = self._monotonic()
            native_remaining = max(0, math.ceil(native_deadline / 1_000_000 - evaluated_monotonic))
            daily_remaining = min(daily_remaining, native_remaining)
        return daily_remaining

    @staticmethod
    def _check_caller(config: Configuration, caller_uid: int) -> None:
        if caller_uid != config.kiosk_uid:
            raise AccessDenied("caller is not the configured request station")

    @staticmethod
    def _saved_time_request_kind(config: Configuration, caller_uid: int, target_uid: int) -> str:
        if caller_uid != 0 and caller_uid == config.kiosk_uid:
            return "kiosk"
        if caller_uid >= MIN_MANAGED_UID and caller_uid == target_uid:
            return "child"
        raise AccessDenied("caller cannot manage this account's saved time")

    def _resolve_saved_time_session(
            self, caller_uid: int, sender: str, *, expected: SessionState | None = None,
            after_own_lock: bool = False,
            timeout_seconds: float = SESSION_LOCK_TIMEOUT_SECONDS) -> SessionState:
        if self._sessions is None:
            raise AccessDenied("caller session is unavailable")
        try:
            session = self._sessions.resolve(sender, timeout_seconds=timeout_seconds)
        except Exception as error:
            raise AccessDenied("caller session is unavailable") from error
        if (session is None or session.uid != caller_uid or session.remote or
                session.state == "closing" or
                (not after_own_lock and (not session.active or session.locked)) or
                (expected is not None and not _same_session(session, expected))):
            raise AccessDenied("caller has no eligible local session")
        return session

    def _saved_time_context(self, caller_uid: int, sender: str, target_uid: int) -> SavedTimeContext:
        config = self._load_config()
        request_kind = self._saved_time_request_kind(config, caller_uid, target_uid)
        target, preferences = self._saved_time_target(config, target_uid)
        session = self._resolve_saved_time_session(caller_uid, sender)
        return SavedTimeContext(caller_uid, sender, request_kind, target, preferences, session)

    def _saved_time_target(self, config: Configuration, target_uid: int) -> tuple[UserAccount, dict]:
        target = self._grant_mutation_target(config, target_uid)
        preferences = self._load_request_preferences(target.uid)
        if not preferences["parent_control_enabled"]:
            raise AccessDenied("parent control is not enabled for this account")
        return target, preferences

    def _recheck_saved_time_context(self, context: SavedTimeContext, record: GrantRecord) -> None:
        config = self._load_config()
        self._recheck_saved_time_selection(config, context, record)
        if context.lock_capture_complete:
            self._require_no_unlocked_child_desktops(context)
        self._resolve_saved_time_session(
            context.caller_uid, context.sender, expected=context.session,
            after_own_lock=context.lock_capture_complete and context.request_kind == "child",
        )
        if not self._caller_alive(context.sender):
            raise AccessDenied("caller disconnected during request")

    def _recheck_saved_time_selection(self, config: Configuration, context: SavedTimeContext,
                                      record: GrantRecord, *,
                                      approver: UserAccount | None = None) -> None:
        request_kind = self._saved_time_request_kind(config, context.caller_uid, context.target.uid)
        if request_kind != context.request_kind:
            raise AccessDenied("caller role changed during request")
        self._check_record_account(record, config=config)
        if approver is not None and self._approver(config, approver.uid) != approver:
            raise AccessDenied("selected approver changed during authorization")
        if self._load_request_preferences(context.target.uid) != context.preferences:
            raise AccessDenied("preferences changed during request")

    @buffer_saved_time_logs
    def pause_grant(self, caller_uid: int, sender: str, target_uid: int, revision: int) -> None:
        if not self._acquire_request_lock("pause"):
            raise Busy("another request is already in progress")
        try:
            if type(revision) is not int or not 0 <= revision <= UINT64_MAX:
                raise InvalidRequest("grant record revision is invalid")
            context = self._saved_time_context(caller_uid, sender, target_uid)
            record = self._recover_grant_record_locked(context.target, revision=revision)
            with self._accounts.bind_grant_mutations(record.uid, record.username):
                try:
                    self._pause_grant_locked(context, record)
                except GrantAccountChanged:
                    self._reject_invalid_grant(record)
        finally:
            self._release_request_lock()

    @buffer_saved_time_logs
    def use_saved_time(self, caller_uid: int, sender: str, target_uid: int, revision: int) -> None:
        if not self._acquire_request_lock("redemption"):
            raise Busy("another request is already in progress")
        try:
            if type(revision) is not int or not 0 <= revision <= UINT64_MAX:
                raise InvalidRequest("grant record revision is invalid")
            context = self._saved_time_context(caller_uid, sender, target_uid)
            record = self._recover_grant_record_locked(context.target, revision=revision)
            if record.saved is None:
                raise Stale("no saved time remains")
            with self._accounts.bind_grant_mutations(record.uid, record.username):
                try:
                    self._use_saved_time_locked(context, record)
                except GrantAccountChanged:
                    self._reject_invalid_grant(record)
        finally:
            self._release_request_lock()

    def _use_saved_time_locked(self, context: SavedTimeContext, record: GrantRecord) -> None:
        outcome, seconds = "failed", 0
        try:
            self._redeem_saved_time_locked(context, record)
        except (RecoveryPending, RollbackFailure):
            outcome = "pending"
            raise
        else:
            outcome, seconds = "committed", record.saved.seconds
        finally:
            log_saved_time("grant.redemption", surface=context.request_kind,
                           outcome=outcome, redeemed_seconds=seconds)

    def _redeem_saved_time_locked(self, context: SavedTimeContext, record: GrantRecord) -> None:
        uid = context.target.uid
        correlation_id = str(uuid.uuid4())
        allow_soft = record.saved.allow_soft_blocked_apps
        desired_filter, termination_patterns = self._approval_app_policy(
            uid, context.preferences, allow_soft,
        )
        source = self._read_live_grant(uid)
        capture = self._capture_use_saved_time_daily_remaining(context, record)
        issued_at = int(capture.evaluated_at.timestamp())
        if not 0 < issued_at <= UINT64_MAX:
            raise BackendFailure("redemption issuance is outside the supported range")
        daily = capture.daily_remaining_seconds
        try:
            remaining = remaining_seconds(source, issued_at) if source[1] else 0
        except ValueError as error:
            raise BackendFailure("remaining-time grant is outside the supported range") from error
        if running_mode(record, source, remaining) == "none":
            remaining = 0
        duration = calculate_active_extension_seconds(daily, remaining, record.saved.seconds)
        if duration > MAX_REQUEST_SECONDS:
            raise InvalidRequest("using saved time would exceed the grant limit")
        destination = (issued_at, duration)
        intent = RedeemIntent(source, destination, allow_soft,
                              new_grant_is_fixed(record, source, daily, remaining),
                              activate_child_extension=context.request_kind == "kiosk")
        attempt = _RedeemAttempt(record, intent)

        def recheck():
            self._recheck_saved_time_context(capture.context, record)
            if self._load_saved_time_record(context.target) != record:
                raise Stale("grant record changed while preparing the redemption")
            return True

        try:
            self._apply(uid, context.preferences, desired_filter, destination, correlation_id,
                        termination_patterns, admit=recheck,
                        activate_child_extension=intent.activate_child_extension, redeem=attempt)
        except _GrantAccountInvalidated:
            raise
        except BrokerError as error:
            if attempt.record.intent is None:
                raise
            try:
                _, committed = self._resolve_redeem_intent(attempt, correlation_id)
            except RecoveryPending as recovery_error:
                if isinstance(error, RollbackFailure):
                    raise error from recovery_error
                raise
            if not committed:
                raise BackendFailure("an external grant superseded the redemption") from error
        else:
            self._finish_redeem_intent(attempt.record, committed=True)

    def _load_saved_time_record(self, target: UserAccount) -> GrantRecord:
        if self._grant_store is None:
            raise BackendFailure("saved-time store is unavailable")
        try:
            record = self._grant_store.load(target.uid, target.username)
        except GrantAccountError as error:
            if error.record is not None:
                self._fence_grant(error.record)
            raise Stale("saved time belonged to a previous account") from error
        except GrantStoreError as error:
            raise BackendFailure("saved-time record is unavailable") from error
        if self._grant_is_fenced(record, discard_stale=True):
            raise Stale("saved time belonged to a previous account")
        return record

    def _grant_is_fenced(self, record: GrantRecord, *, discard_stale: bool = False) -> bool:
        with self._grant_fence_lock:
            revisions = self._grant_fences.get(record.uid)
            if revisions is None:
                return False
            first, last = revisions
            if discard_stale and last < record.revision:
                del self._grant_fences[record.uid]
            return first <= record.revision <= last

    def _fence_grant(self, record: GrantRecord, *, through_revision: int | None = None) -> None:
        if record.revision:
            with self._grant_fence_lock:
                last = through_revision if through_revision is not None else record.revision
                self._fence_grant_revisions_locked(record.uid, record.revision, last)

    def _fence_grant_revisions_locked(self, uid: int, first: int, last: int) -> None:
        current = self._grant_fences.get(uid)
        if current is None or first > current[1]:
            self._grant_fences[uid] = (first, last)
        elif last >= current[0]:
            self._grant_fences[uid] = (min(first, current[0]), max(last, current[1]))

    def _note_grant_publication(self, previous: GrantRecord, revision: int, *, uncertain: bool = False) -> bool:
        """Advance observations of state carried by this write and check its fence."""
        with self._grant_fence_lock:
            self._grant_publications += 1
            for observation in self._grant_observations.get(previous.uid, ()):
                if not observation.first_revision <= previous.revision <= observation.last_revision:
                    continue
                if observation.first_revision < previous.revision and not previous.has_state:
                    # An ambiguous predecessor cannot attach to a later
                    # approval through an empty, independently cleared row.
                    observation.last_revision = previous.revision - 1
                elif uncertain:
                    observation.last_revision = max(observation.last_revision, revision)
                else:
                    observation.first_revision = observation.last_revision = revision
            fence = self._grant_fences.get(previous.uid)
            return fence is not None and fence[0] <= revision and previous.revision <= fence[1]

    def _write_grant_record(self, previous: GrantRecord, replacement: GrantRecord) -> GrantRecord:
        """Carry forward a generation only if it survived concurrent identity observation."""
        if self._grant_is_fenced(previous):
            self._reject_invalid_grant(previous)
        try:
            written = self._grant_store.write(replacement)
        except GrantStoreError as error:
            successor = replace(replacement, revision=previous.revision + 1)
            if self._note_grant_publication(previous, successor.revision, uncertain=True):
                # An unsuccessful directory sync can leave our successor
                # visible. Block both possible revisions until we can read it.
                self._fence_grant(previous, through_revision=successor.revision)
                try:
                    observed = self._grant_store.load_record(previous.uid)
                except GrantStoreError:
                    raise _GrantAccountInvalidated("saved-time account changed") from error
                if observed in (previous, successor):
                    self._reject_invalid_grant(observed)
                raise _GrantAccountInvalidated("saved-time account changed") from error
            raise
        if self._note_grant_publication(previous, written.revision):
            self._reject_invalid_grant(written)
        return written

    def _read_grant_record_for_status(
            self, config: Configuration, target_uid: int, *, schedule_recovery: Callable[[int], None],
            expected_revision: int | None = None,
    ) -> tuple[UserAccount, GrantRecord]:
        """Read and validate a status record after caller authorization."""
        if self._request_lock.locked():
            raise Busy("another request is already in progress")
        if type(target_uid) is not int or not 0 <= target_uid <= UINT32_MAX:
            raise InvalidRequest("target UID is invalid")
        if self._grant_store is None:
            raise BackendFailure("saved-time store is unavailable")
        # Pair the disk snapshot with registration without making a writer
        # hold the observation lock across disk I/O.
        with self._grant_fence_lock:
            publications = self._grant_publications
        try:
            stored_record = self._grant_store.load_record(target_uid)
        except GrantStoreError as error:
            raise BackendFailure("saved-time record is unavailable") from error
        observation = None
        with self._grant_fence_lock:
            revision = stored_record.revision if stored_record is not None else 0
            if (publications != self._grant_publications or
                    (expected_revision is not None and revision != expected_revision)):
                raise Busy("another request is already in progress")
            if stored_record is not None:
                observation = _GrantObservation(stored_record.revision, stored_record.revision)
                self._grant_observations.setdefault(target_uid, set()).add(observation)

        def invalidate():
            if observation is None:
                return
            with self._grant_fence_lock:
                self._fence_grant_revisions_locked(
                    target_uid, observation.first_revision, observation.last_revision,
                )
            schedule_recovery(target_uid)

        try:
            target = self._target(
                config, target_uid, on_invalid=invalidate, unavailable_is_backend_failure=True,
            )
            record = stored_record or GrantRecord(target_uid, target.username)
            if record.username != target.username or self._grant_is_fenced(record):
                invalidate()
                raise RecoveryPending("a previous account's saved time is awaiting invalidation")
            if self._request_lock.locked():
                raise Busy("another request is already in progress")
            if record.intent is not None or record.bridge_repair is not None:
                schedule_recovery(target_uid)
                raise RecoveryPending("a saved-time transfer is awaiting recovery")
            return target, record
        finally:
            if observation is not None:
                with self._grant_fence_lock:
                    observations = self._grant_observations[target_uid]
                    observations.remove(observation)
                    if not observations:
                        del self._grant_observations[target_uid]

    def _grant_mutation_target(self, config: Configuration, target_uid: int) -> UserAccount:
        return self._target(config, target_uid, on_invalid=lambda: self._invalidate_grant(target_uid))

    def _invalidate_grant(self, uid: int, *, expected: GrantRecord | None = None) -> None:
        if self._grant_store is None:
            return
        try:
            record = self._grant_store.load_record(uid)
        except GrantStoreError as error:
            raise BackendFailure("saved-time record could not be cleared") from error
        if (record is not None and (expected is None or record == expected) and
                (record.has_state or self._grant_is_fenced(record))):
            self._fence_grant(record)
            self._clear_saved_time(uid, record.username)

    def _reject_invalid_grant(self, record: GrantRecord) -> None:
        self._fence_grant(record)
        try:
            self._invalidate_grant(record.uid, expected=record)
        except BackendFailure as error:
            raise _GrantAccountInvalidated("saved-time account changed") from error
        raise _GrantAccountInvalidated("saved-time account changed")

    def _recover_grant_record_locked(
            self, target: UserAccount, *, revision: int | None = None,
    ) -> GrantRecord | None:
        if self._grant_store is None and revision is None:
            return None
        try:
            record = self._load_saved_time_record(target)
        except Stale:
            record = self._clear_saved_time(target.uid, target.username)
            self._check_grant_account(self._load_config(), target)
            changed = True
        else:
            if revision is not None and record.revision != revision:
                raise Stale("grant record changed since it was read")
            changed = record.intent is not None or record.bridge_repair is not None
            if record.bridge_repair is not None:
                record = self._repair_grant_bridge(record)
            elif isinstance(record.intent, PauseIntent):
                self._active_pause = _ActivePause(target.uid)
                with self._accounts.bind_grant_mutations(record.uid, record.username):
                    record = self._recover_pause_intent(record)
            elif isinstance(record.intent, RedeemIntent):
                record = self._recover_redeem_intent(record)
        if revision is not None and (changed or record.revision != revision):
            raise Stale("grant record changed since it was read")
        return record

    def recover_grant(self, target_uid: int, *, at_startup: bool = False) -> None:
        """Attempt one freshly read record for startup or a queued status read."""
        if self._grant_store is None or not self._acquire_request_lock("grant-recovery"):
            return
        try:
            record = self._grant_store.load_record(target_uid) if at_startup else None
            if at_startup and (record is None or not record.has_state):
                return
            config = self._load_config()
            if record is None:
                target = self._grant_mutation_target(config, target_uid)
            else:
                target = self._target(config, target_uid, on_invalid=lambda: self._reject_invalid_grant(record))
                if target.username != record.username:
                    self._fence_grant(record)
            self._recover_grant_record_locked(target)
        except Exception as error:
            record_exception(error)
        finally:
            self._release_request_lock()

    def recover_grants_at_startup(self) -> None:
        if self._grant_store is None:
            return
        try:
            uids = self._grant_store.record_uids()
        except GrantStoreError as error:
            record_exception(error)
            return
        for uid in uids:
            self.recover_grant(uid, at_startup=True)

    def _clear_saved_time(self, uid: int, username: str) -> GrantRecord:
        try:
            record = self._grant_store.clear(uid, username)
        except GrantStoreError as error:
            raise BackendFailure("saved-time record could not be cleared") from error
        with self._grant_fence_lock:
            self._grant_publications += 1
            for observation in self._grant_observations.get(uid, ()):
                if observation.first_revision < record.revision <= observation.last_revision:
                    observation.last_revision = record.revision - 1
            revisions = self._grant_fences.get(uid)
            if revisions is not None and revisions[1] <= record.revision:
                del self._grant_fences[uid]
        return record

    def _withdraw_saved_time(self, config: Configuration, target: UserAccount) -> None:
        if self._grant_store is None:
            return
        try:
            record = self._grant_store.load_record(target.uid)
        except GrantStoreError as error:
            raise BackendFailure("saved-time record is unavailable") from error
        if record is not None and record.username != target.username:
            self._fence_grant(record)
        elif record is not None and not self._grant_is_fenced(record):
            if record.bridge_repair is not None:
                self._repair_grant_bridge(record)
                self._check_grant_account(config, target)
                return
            if isinstance(record.intent, RedeemIntent) and record.intent.time_state is not None:
                self._check_record_account(record, config=config)
                repair = BridgeRepair(record.intent.destination, record.intent.time_state)
                try:
                    withdrawn = self._write_grant_record(record, GrantRecord(
                        record.uid, record.username, record.revision, bridge_repair=repair,
                    ))
                except GrantStoreError as error:
                    raise RecoveryPending("saved-time withdrawal durability is uncertain") from error
                self._repair_grant_bridge(withdrawn, durable=True)
                self._check_grant_account(config, target)
                return
        self._clear_saved_time(target.uid, target.username)
        self._check_grant_account(config, target)

    def _repair_grant_bridge(self, record: GrantRecord, *, durable: bool = False) -> GrantRecord:
        with _report_grant_recovery("time-settings"):
            result = self._restore_grant_bridge(record, durable=durable)
        log_saved_time("grant.recovery", stage="time-settings", outcome="restored")
        return result

    def _restore_grant_bridge(self, record: GrantRecord, *, durable: bool) -> GrantRecord:
        try:
            if not durable:
                self._grant_store.confirm_durable(record)
            self._check_record_account(record)
            preferences = self._load_request_preferences(record.uid)
            with self._accounts.bind_grant_mutations(record.uid, record.username):
                self._reconcile_redeem_time_state(record, preferences, destination=None, bridge_only=True)
            return self._clear_saved_time(record.uid, record.username)
        except GrantAccountChanged:
            self._reject_invalid_grant(record)
        except _GrantAccountInvalidated:
            raise
        except Exception as error:
            raise RecoveryPending("redemption time settings could not be restored") from error

    def _read_live_grant(self, uid: int, *, deadline: float | None = None) -> GrantTuple:
        bounds = {} if deadline is None else {"deadline": deadline}
        try:
            if deadline is not None and self._monotonic() >= deadline:
                raise TimeoutError("extension read window elapsed")
            issued, duration = self._accounts.get_extension(uid, **bounds)
            if deadline is not None and self._monotonic() >= deadline:
                raise TimeoutError("extension read window elapsed")
        except GrantAccountChanged:
            raise
        except Exception as error:
            raise BackendFailure("remaining-time grant is unavailable") from error
        if (type(issued) is not int or not 0 <= issued <= UINT64_MAX or
                type(duration) is not int or not 0 <= duration <= UINT32_MAX):
            raise BackendFailure("remaining-time grant is invalid")
        return issued, duration

    def _pause_grant_locked(self, context: SavedTimeContext, record: GrantRecord) -> GrantRecord:
        outcome, seconds = "failed", 0
        try:
            result = self._transfer_pause_locked(context, record)
        except _NoPausableTime:
            outcome = "not-pausable"
            raise
        except RecoveryPending:
            outcome = "pending"
            raise
        else:
            outcome = "committed"
            seconds = result.saved.seconds - (record.saved.seconds if record.saved else 0)
            return result
        finally:
            log_saved_time("grant.pause", surface=context.request_kind,
                           outcome=outcome, transferred_seconds=seconds)

    def _transfer_pause_locked(self, context: SavedTimeContext, record: GrantRecord) -> GrantRecord:
        """Pause a fixed grant under the transaction lock using a validated record."""
        if record.intent is not None:
            raise RecoveryPending("a saved-time transfer is awaiting recovery")
        uid = context.target.uid
        source = self._read_live_grant(uid)
        try:
            remaining = remaining_seconds(source, int(self._now().timestamp()))
        except ValueError as error:
            raise BackendFailure("remaining-time grant is outside the supported range") from error
        if running_mode(record, source, remaining) != "fixed":
            raise _NoPausableTime("there is no running fixed grant to pause")

        self._active_pause = _ActivePause(uid)
        capture = self._capture_pause_daily_remaining(context, record)
        current = self._load_saved_time_record(context.target)
        if current != record or self._read_live_grant(uid) != source:
            raise Stale("grant changed while capturing completed usage")
        self._recheck_saved_time_context(capture.context, record)

        # The wire tuple ends on a whole wall-clock second. Charge all work
        # after the transfer anchor to the same margin on both clocks.
        anchor_at, anchor_monotonic = capture.transfer_anchor
        anchor_timestamp = anchor_at.timestamp()
        boundary = int(anchor_timestamp) + TRANSFER_MARGIN_SECONDS
        transfer_deadline = anchor_monotonic + (boundary - anchor_timestamp)
        try:
            transferable = beyond_daily_seconds(
                capture.daily_remaining_seconds, remaining_seconds(source, boundary),
            )
        except ValueError as error:
            raise BackendFailure("pause balance is outside the supported range") from error
        if transferable == 0:
            raise _NoPausableTime("no approved time beyond the daily allowance remains to save")
        shortened = (source[0], boundary - source[0])
        if shortened[1] <= 0:
            raise BackendFailure("grant was issued after the pause boundary")
        try:
            saved_seconds = merged_saved_seconds(
                record.saved.seconds if record.saved is not None else 0, transferable,
            )
        except ValueError as error:
            raise InvalidRequest("pause would exceed the saved-time limit") from error
        app_choice = record.saved if record.saved is not None else record.fixed
        intent = PauseIntent(source, shortened,
                             SavedBalance(saved_seconds, app_choice.allow_soft_blocked_apps))

        if self._extension_window_elapsed(transfer_deadline, boundary):
            raise BackendFailure("completed usage is too old for the pause transfer", expected=True)
        try:
            pending = self._write_grant_record(record, replace(record, intent=intent))
        except GrantStoreError as error:
            # Replacement may have happened before the directory sync failed.
            # Never shorten the live grant without a confirmed durable intent.
            try:
                observed = self._grant_store.load(uid, context.target.username)
            except GrantStoreError:
                raise RecoveryPending("pause intent durability is uncertain") from error
            if observed == record:
                raise BackendFailure("pause intent could not be stored") from error
            raise RecoveryPending("pause intent durability is uncertain") from error

        try:
            # AccountsService has no conditional Set. Recheck the source
            # after syncing the intent to narrow the race with external writes.
            if self._extension_window_elapsed(transfer_deadline, boundary):
                raise TimeoutError("extension write window elapsed")
            live = self._read_live_grant(uid, deadline=transfer_deadline)
            if live == source:
                if self._grant_is_fenced(pending):
                    self._reject_invalid_grant(pending)
                self._write_extension(uid, shortened, deadline=transfer_deadline,
                                      wall_deadline=boundary)
                live = shortened
        except GrantAccountChanged:
            self._reject_invalid_grant(pending)
        except _GrantAccountInvalidated:
            raise
        except Exception as error:
            record_exception(error)
            resolved = self._recover_pause_intent(pending, transfer_deadline=transfer_deadline)
            if resolved.fixed is None or not resolved.fixed.ended_by_pause:
                raise BackendFailure("the shortened grant could not be verified") from error
        else:
            resolved = self._finish_pause_intent(pending, live)
            if live != shortened:
                raise BackendFailure("the running grant changed before it could be shortened")
        return resolved

    def _wait_for_pause_boundary(self, boundary: int, transfer_deadline: float | None) -> None:
        wall_delay = boundary - self._now().timestamp()
        delay = wall_delay
        if transfer_deadline is not None:
            delay = max(delay, transfer_deadline - self._monotonic())
        if delay > TRANSFER_MARGIN_SECONDS:
            raise RecoveryPending("pause boundary is outside the recovery wait window")
        if delay > 0:
            self._sleep(delay)
        if (self._now().timestamp() < boundary or
                (transfer_deadline is not None and self._monotonic() < transfer_deadline)):
            raise RecoveryPending("pause boundary has not passed")

    def _recover_pause_intent(self, record: GrantRecord, *,
                              transfer_deadline: float | None = None) -> GrantRecord:
        """Resolve a durable pause intent under the transaction lock."""
        with _report_grant_recovery("pause"):
            return self._resolve_pause_intent(record, transfer_deadline=transfer_deadline)

    def _resolve_pause_intent(self, record: GrantRecord, *, transfer_deadline: float | None) -> GrantRecord:
        intent = record.intent
        assert isinstance(intent, PauseIntent)
        boundary = sum(intent.destination)
        try:
            if transfer_deadline is not None:
                self._wait_for_pause_boundary(boundary, transfer_deadline)
            for attempt in range(2):
                # A read begun before B is never evidence that the write
                # failed, even when its reply arrives after B.
                read_started = self._now().timestamp()
                deadline = self._monotonic() + TRANSFER_MARGIN_SECONDS
                live = self._read_live_grant(record.uid, deadline=deadline)
                if live != intent.source or (
                        read_started >= boundary and self._now().timestamp() >= boundary):
                    break
                if attempt or transfer_deadline is not None:
                    raise RecoveryPending("pause boundary has not passed")
                self._wait_for_pause_boundary(boundary, None)
        except GrantAccountChanged:
            self._reject_invalid_grant(record)
        except BackendFailure as error:
            raise RecoveryPending("pause outcome could not be verified") from error
        result = self._finish_pause_intent(record, live)
        outcome = "committed" if live == intent.destination else (
            "source-retained" if live == intent.source else "superseded")
        log_saved_time("grant.recovery", stage="pause", outcome=outcome)
        return result

    def _finish_pause_intent(self, record: GrantRecord, live: GrantTuple) -> GrantRecord:
        intent = record.intent
        result = replace(record, intent=None)
        if live == intent.destination:
            result = replace(result, saved=intent.saved,
                             fixed=replace(record.fixed, grant=live, ended_by_pause=True))
        try:
            self._check_record_account(record)
            return self._write_grant_record(record, result)
        except _GrantAccountInvalidated:
            raise
        except (BrokerError, GrantStoreError) as error:
            # A visible replacement is insufficient to confirm durability.
            # Either version can safely be read or recovered on the next call.
            raise RecoveryPending("pause result durability is uncertain") from error

    def _capture_pause_daily_remaining(self, context: SavedTimeContext, record: GrantRecord) -> DailyCapture:
        return self._capture_saved_time_daily_remaining(
            context, record, operation_kind="pause", lock_before_capture=True,
        )

    def _capture_use_saved_time_daily_remaining(self, context: SavedTimeContext, record: GrantRecord) -> DailyCapture:
        return self._capture_saved_time_daily_remaining(
            context, record, operation_kind="redemption", lock_before_capture=context.request_kind == "kiosk",
        )

    def _capture_saved_time_daily_remaining(
            self, context: SavedTimeContext, record: GrantRecord, *,
            operation_kind: str, lock_before_capture: bool) -> DailyCapture:
        self._recheck_saved_time_context(context, record)
        uid = context.target.uid
        usage = None
        transfer_anchor = None
        witnesses = []
        if lock_before_capture:
            own_session = context.session if context.request_kind == "child" else None
            if own_session is not None and own_session.kind not in GRAPHICAL_SESSION_TYPES:
                raise AccessDenied("pausing requires the child's local graphical session")
            targets = self._unlocked_child_desktops(context)
            if own_session is not None:
                targets += (own_session,)
            seen_ends = set()
            for session in targets:
                usage, lock_anchor = self._lock_and_observe_usage(
                    context, session, seen_ends, witnesses, operation_kind=operation_kind,
                )
                if session is own_session:
                    # The caller can unlock while the lock's usage is still being collected.
                    transfer_anchor = lock_anchor
        if usage is None:
            usage = self._saved_time_usage(uid)
        if transfer_anchor is None:
            observed_monotonic = self._monotonic()
            transfer_anchor = (self._now(), observed_monotonic)
        if witnesses:
            coverage = _merge_usage_intervals(usage)
            if not all(any(start <= first and last <= end for start, end in coverage)
                       for first, last in witnesses):
                raise BackendFailure("completed usage changed during desktop locking")
        if lock_before_capture:
            self._require_no_unlocked_child_desktops(context)

        native_deadline = None
        if not lock_before_capture:
            try:
                native_deadline = self._native_deadline(uid, context.preferences)
            except NativeDeadlineSuspended as error:
                raise Busy("native time is suspended while the child session is inactive") from error
            except Exception as error:
                raise BackendFailure("native remaining time is unavailable") from error
        evaluated_at = self._now()
        status = self._time_status_from_usage(
            context.preferences, usage, 0, 0, 0, evaluated_at, native_deadline=native_deadline,
        )
        return DailyCapture(replace(context, lock_capture_complete=lock_before_capture),
                            evaluated_at, status.daily_allowance_remaining_seconds,
                            transfer_anchor)

    def _require_no_unlocked_child_desktops(self, context: SavedTimeContext) -> None:
        if self._unlocked_child_desktops(context):
            raise BackendFailure("child desktop is unlocked after usage capture")

    def _unlocked_child_desktops(self, context: SavedTimeContext) -> tuple[SessionState, ...]:
        uid = context.target.uid
        try:
            sessions = self._sessions.for_user(uid, timeout_seconds=SESSION_LOCK_TIMEOUT_SECONDS)
        except Exception as error:
            raise BackendFailure("child sessions are unavailable") from error
        if any(session.uid != uid for session in sessions):
            raise BackendFailure("child session owner changed during request")
        own_session = context.session if context.request_kind == "child" else None
        unlocked = tuple(session for session in sessions
                         if not session.remote and session.kind in GRAPHICAL_SESSION_TYPES
                         and not session.locked
                         and (own_session is None or not _same_session(session, own_session)))
        if context.request_kind == "kiosk" and any(session.active for session in unlocked):
            raise DesktopInUse("child desktop is active and unlocked")
        return unlocked

    def _saved_time_usage(self, uid: int, *, deadline: float | None = None) -> UsageIntervals:
        timeout = None if deadline is None else self._lock_time_remaining(deadline)
        if self._timer_usage is None:
            raise BackendFailure("completed usage is unavailable")
        try:
            usage = self._timer_usage.query_usage(uid, timeout_seconds=timeout)
            valid = all(isinstance(entry, tuple) and len(entry) == 2 and
                        _valid_usage_interval(*entry) for entry in usage)
        except Exception as error:
            raise BackendFailure("completed usage is unavailable") from error
        if not valid:
            raise BackendFailure("timer usage returned an invalid interval")
        if deadline is not None:
            self._lock_time_remaining(deadline)
        return usage

    def _lock_time_remaining(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise BackendFailure("desktop lock or completed usage timed out")
        return remaining

    def _read_lock_session(self, session: SessionState, deadline: float) -> SessionState:
        timeout = self._lock_time_remaining(deadline)
        try:
            current = self._sessions.get(session.path, timeout_seconds=timeout)
        except Exception as error:
            raise BackendFailure("desktop session is unavailable") from error
        self._lock_time_remaining(deadline)
        if (not _same_session(current, session) or current.remote or current.state == "closing" or
                current.kind != session.kind):
            raise BackendFailure("desktop session changed during locking")
        return current

    def _lock_and_observe_usage(
            self, context: SavedTimeContext, session: SessionState,
            seen_ends: set[int], witnesses: list[tuple[int, int]], *, operation_kind: str,
    ) -> tuple[UsageIntervals, tuple[datetime, float]]:
        uid = context.target.uid
        deadline = self._monotonic() + SESSION_LOCK_TIMEOUT_SECONDS
        # QueryUsage merges overlaps and has second precision. Give each lock
        # a new end timestamp, including one second of API rounding tolerance.
        while True:
            baseline = self._saved_time_usage(uid, deadline=deadline)
            seen_ends.update(end for _, end in baseline)
            now = self._now().timestamp()
            # After the wall clock moves back, a previously seen record may
            # be in the future. Keep it as old evidence without waiting for it.
            watermark = max((end for end in seen_ends if end <= now), default=-1)
            delay = watermark + 2 - now
            if delay <= 0:
                break
            self._sleep(min(delay, self._lock_time_remaining(deadline)))
        caller = self._resolve_saved_time_session(
            context.caller_uid, context.sender, expected=context.session,
            timeout_seconds=self._lock_time_remaining(deadline),
        )
        if context.request_kind == "child" and caller.kind not in GRAPHICAL_SESSION_TYPES:
            raise AccessDenied("pausing requires the child's local graphical session")
        if not _same_session(caller, session):
            current = self._read_lock_session(session, deadline)
            if current.locked:
                raise BackendFailure("child desktop locked before usage could be captured")
            if context.request_kind == "kiosk" and current.active:
                raise DesktopInUse("child desktop is active and unlocked")
        lock_monotonic = self._monotonic()
        lock_at = self._now()
        earliest_end = int(lock_at.timestamp()) - 1
        if earliest_end <= watermark:
            raise BackendFailure("wall clock changed before desktop locking")
        timeout = self._lock_time_remaining(deadline)
        outcome = "request-failed"
        try:
            try:
                self._sessions.lock(session.session_id, timeout_seconds=timeout)
            except Exception as error:
                raise BackendFailure("could not lock desktop session") from error
            outcome = "lock-unconfirmed"
            while not self._read_lock_session(session, deadline).locked:
                self._sleep(min(SESSION_LOCK_POLL_SECONDS, self._lock_time_remaining(deadline)))

            outcome = "usage-unconfirmed"
            while True:
                usage = self._saved_time_usage(uid, deadline=deadline)
                observed_at = int(self._now().timestamp())
                self._lock_time_remaining(deadline)
                witness = next(((start, end) for start, end in usage
                                if earliest_end <= end <= observed_at and end not in seen_ends), None)
                seen_ends.update(end for _, end in usage)
                if witness is not None:
                    witnesses.append(witness)
                    outcome = "usage-observed"
                    return usage, (lock_at, lock_monotonic)
                self._sleep(min(SESSION_LOCK_POLL_SECONDS, self._lock_time_remaining(deadline)))
        finally:
            log_saved_time("grant.lock", operation=operation_kind, surface=context.request_kind, outcome=outcome)

    @staticmethod
    def _eligible(config: Configuration, user: UserAccount) -> bool:
        return (
            MIN_MANAGED_UID <= user.uid <= UINT32_MAX and
            user.uid != config.kiosk_uid and
            user.is_local and not user.is_system and not user.is_admin
        )

    def _is_admin(self, caller_uid: int, *, unavailable_is_backend_failure: bool = False) -> bool:
        if caller_uid == 0:
            return True
        try:
            user = self._accounts.get_user(caller_uid)
            return user.is_admin and user.is_local
        except AccountMissing:
            return False
        except Exception as error:
            if unavailable_is_backend_failure:
                raise BackendFailure("caller account is unavailable") from error
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

    def diagnostic_user_languages(self, caller_uid: int) -> dict:
        """Project personal selections without exporting identities or raw locales."""
        self.authorize_diagnostic_export(caller_uid)
        deadline = time.monotonic() + 5
        try:
            config = self._load_config()
            status, users = self._accounts.diagnostic_user_roles(
                excluded_uid=config.kiosk_uid, deadline=deadline, limit=MAX_LANGUAGE_USERS)
        except Exception:
            return {"status": "unavailable", "users": []}
        selections = []
        for uid, role in users:
            if len(selections) >= MAX_LANGUAGE_USERS or time.monotonic() >= deadline:
                status = "partial"
                break
            try:
                saved = self._preferences.load(uid)["personal"]["language"]
                # Storage accepts future language syntax; export accepts only
                # reviewed catalogue values, never arbitrary private subtags.
                language = "unset" if saved == "" else saved if saved in LANGUAGE_IDS else "other"
            except Exception:
                language, status = "unavailable", "partial"
            selections.append(("Parent" if role == "administrator" else "Child", language))
        # Labels have no identity mapping, even transiently in the archive.
        # Sort only projected values, never names, UIDs or account discovery order.
        ordinals, rows = {"Parent": 0, "Child": 0}, []
        for role, language in sorted(selections):
            ordinals[role] += 1
            rows.append({"user": f"[{role} {ordinals[role]}]", "language": language})
        return {"status": status, "users": rows}

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
        if not self._acquire_request_lock("session-policy-read"):
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
            self._release_request_lock()

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

    def get_child_monitors_config(self, caller_uid: int, target_uid: int) -> str:
        """Return the selected child's saved desktop monitor layout for the kiosk."""
        target_uid = self._kiosk_language_target(caller_uid, target_uid)
        try:
            return self._monitors_reader(target_uid)
        except (OSError, ValueError, KeyError) as error:
            raise BackendFailure("child monitor configuration is unavailable") from error

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

    def _target(self, config: Configuration, target_uid: int, *,
                on_invalid: Callable[[], None] | None = None,
                unavailable_is_backend_failure: bool = False) -> UserAccount:
        if type(target_uid) is not int or not 0 <= target_uid <= UINT32_MAX:
            raise InvalidRequest("target UID is invalid")
        try:
            user = self._accounts.get_user(target_uid)
        except GrantAccountChanged:
            if on_invalid is not None:
                on_invalid()
            raise
        except AccountMissing as error:
            if on_invalid is not None:
                on_invalid()
            raise InvalidRequest("selected account is unavailable") from error
        except Exception as error:
            if unavailable_is_backend_failure:
                raise BackendFailure("selected account is unavailable") from error
            raise InvalidRequest("selected account is unavailable") from error
        if user.uid != target_uid:
            raise AccessDenied("selected account identity changed")
        if not self._eligible(config, user):
            if on_invalid is not None:
                on_invalid()
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
        if not self._acquire_request_lock("app-policy-save"):
            raise Busy("another request is already in progress")
        try:
            return self._set_preferences_locked(caller_uid, target_uid, value)
        finally:
            self._release_request_lock()

    def _set_preferences_locked(
            self, caller_uid: int, target_uid: int, value: object) -> dict:
        config = self._load_config()
        if not self._is_admin(caller_uid):
            raise AccessDenied("administrator access is required")
        target = self._grant_mutation_target(config, target_uid)
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
        self._recover_grant_record_locked(target)
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
            if isinstance(error, BrokerError):
                public_error = error
            else:
                public_error = BackendFailure("blocked applications could not be stopped"
                                              if termination_started else "app filter could not be applied")
            emit_backend_failure(public_error, original=error)
            # Once termination starts, an exited process cannot be restored.
            # Retain the requested canonical policy so every requested block
            # remains enforced and its patterns remain available to the
            # execution-policy reconciler.
            record_exception(error)
            if termination_started:
                LOG.warning("core.013", error_type=error_code(error))
                if public_error is error:
                    raise
                raise public_error from error
            LOG.warning("core.014", error_type=error_code(error))
            try:
                if preferences_saved:
                    self._preferences.save(target.uid, current)
                self._accounts.set_filter(target.uid, old_filter)
                if self._accounts.get_filter(target.uid) != old_filter:
                    raise RuntimeError("app-filter rollback read-back mismatch")
            except Exception as rollback_error:
                failure = RollbackFailure("app-filter rollback could not be verified")
                emit_backend_failure(failure, original=rollback_error)
                LOG.critical("core.015", error_type=error_code(rollback_error))
                raise failure from rollback_error
            if public_error is error:
                raise
            raise public_error from error

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
            if isinstance(error, StoredPreferencesError):
                emit_failure_once("broker", "backend", error)
                record_exception(error)
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
            if isinstance(error, StoredPreferencesError):
                emit_failure_once("broker", "backend", error)
                record_exception(error)
            raise InvalidRequest(str(error)) from error

    def set_parent_control(self, caller_uid: int, target_uid: int, enabled: bool,
                           daily_limit_minutes: int) -> dict:
        if not self._acquire_request_lock("parent-control-save"):
            raise Busy("another request is already in progress")
        try:
            return self._set_parent_control_locked(
                caller_uid, target_uid, enabled, daily_limit_minutes,
            )
        finally:
            self._release_request_lock()

    def _set_parent_control_locked(self, caller_uid: int, target_uid: int, enabled: bool,
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
        target = self._grant_mutation_target(config, target_uid)
        LOG.info("core.016", enabled=enabled, daily_limit_minutes=daily_limit_minutes)
        if self._preferences is None or self._extensions is None:
            raise BackendFailure("extension management is unavailable")
        def entering(value):
            LOG.info("core.parent-control-stage", stage=value, outcome="started")
            return value

        stage = entering("snapshot")
        try:
            current = self._preferences.load(target.uid)
            previous = current["parent_control_enabled"]
            extension_changed = enabled != previous
            if extension_changed:
                self._withdraw_saved_time(config, target)
            else:
                self._recover_grant_record_locked(target)
            desired_filter = (False, blocked_targets(current, False))
            # Known rendering failures must not toggle the extension or change
            # native limits before an inevitable failed save.
            # Commit still reconciles again: this is not a filesystem lock.
            self._accounts.validate_filter(target.uid, desired_filter)
            old_limit_type = self._accounts.get_limit_type(target.uid)
            old_daily_limit = self._accounts.get_daily_limit(target.uid)
            old_daily_schedule = self._accounts.get_daily_schedule(target.uid)
            old_filter = self._accounts.get_filter(target.uid)
            old_extension = self._accounts.get_extension(target.uid)
            LOG.info("core.parent-control-state", previous=previous, requested=enabled, changed=extension_changed)
            if not enabled and not extension_changed:
                issued, duration = old_extension
                if issued <= int(self._now().timestamp()) < issued + duration:
                    # Kiosk approval can enable native limits while the saved
                    # toggle stays off. Preserve its retained-grant policy,
                    # rather than clearing it or disabling limits underneath it.
                    raise BackendFailure("cannot disable native limits while retaining a current grant",
                                         expected=True)
            undo_switch_recovery = None
            if extension_changed:
                stage = entering("extension")
                undo_switch_recovery = self._extensions.set_enabled(
                    target.uid, enabled, recover_global_switch=True,
                )
            preferences_save_started = False
            try:
                desired_limit_type = DAILY_LIMIT_FLAG if enabled else 0
                desired_daily_limit = daily_limit_minutes * 60 if enabled else 0
                # App access is independent from screen time. Reapply the
                # saved blocklist so a toggle cannot retain a temporary
                # soft-block exception (or another stale live filter).
                if not enabled:
                    stage = entering("time-state")
                    self._write_time_state(
                        target.uid, desired_limit_type, desired_daily_limit,
                        old_daily_schedule, (0, 0) if extension_changed else old_extension,
                    )
                else:
                    stage = entering("daily-limit")
                    self._accounts.set_daily_limit(target.uid, desired_daily_limit)
                    if self._accounts.get_daily_limit(target.uid) != desired_daily_limit:
                        raise BackendFailure("daily-limit verification failed")
                    if extension_changed:
                        stage = entering("grant")
                        self._write_extension(target.uid, (0, 0))
                    stage = entering("limit-type")
                    self._accounts.set_limit_type(target.uid, desired_limit_type)
                    if self._accounts.get_limit_type(target.uid) != desired_limit_type:
                        raise BackendFailure("limit-type verification failed")
                stage = entering("app-filter")
                self._accounts.set_filter(target.uid, desired_filter)

                stage = entering("verify")
                if (self._accounts.get_limit_type(target.uid) != desired_limit_type or
                        self._accounts.get_daily_limit(target.uid) != desired_daily_limit or
                        self._accounts.get_daily_schedule(target.uid) != old_daily_schedule):
                    raise BackendFailure("parent-control account verification failed")
                if self._accounts.get_filter(target.uid) != desired_filter:
                    raise BackendFailure("app-filter verification failed")
                if (extension_changed and
                        self._accounts.get_extension(target.uid) != (0, 0)):
                    raise BackendFailure("parent-control account verification failed")

                requested = {**current, "parent_control_enabled": enabled,
                             "daily_time_limit_minutes": daily_limit_minutes}
                preferences_save_started = True
                stage = entering("preferences")
                saved = self._preferences.save(target.uid, requested)
                LOG.info("core.017", enabled=enabled)
                LOG.info("core.parent-control-stage", stage="commit", outcome="accepted")
                return saved
            except Exception as error:
                if isinstance(error, (OSError, RuntimeError, PreferencesError)):
                    if not (isinstance(error, BackendFailure) and error.expected):
                        emit_failure_once("broker", "backend", error)
                else:
                    emit_failure_once("broker", "unexpected", error)
                LOG.warning("core.parent-control-stage", stage=stage, outcome="failed")
                LOG.warning("core.018", error_type=error_code(error))
                record_exception(error)
                rollback_error = None
                try:
                    entering("rollback-account")
                    self._restore(
                        target.uid, old_limit_type, old_daily_limit, old_filter,
                        old_extension, old_daily_schedule, None,
                    )
                    LOG.info("core.parent-control-stage", stage="rollback-account", outcome="accepted")
                except Exception as caught:
                    emit_failure_once("broker", "backend", caught)
                    LOG.error("core.parent-control-stage", stage="rollback-account", outcome="failed")
                    record_exception(caught)
                    rollback_error = caught
                try:
                    if preferences_save_started:
                        entering("rollback-preferences")
                        self._preferences.save(target.uid, current)
                        if self._preferences.load(target.uid) != current:
                            raise RuntimeError("preference rollback read-back mismatch")
                        LOG.info("core.parent-control-stage", stage="rollback-preferences", outcome="accepted")
                except Exception as caught:
                    emit_failure_once("broker", "backend", caught)
                    LOG.error("core.parent-control-stage", stage="rollback-preferences", outcome="failed")
                    record_exception(caught)
                    rollback_error = rollback_error or caught
                try:
                    if extension_changed:
                        entering("rollback-extension")
                        if undo_switch_recovery is not None:
                            undo_switch_recovery()
                        else:
                            self._extensions.set_enabled(target.uid, previous)
                        LOG.info("core.parent-control-stage", stage="rollback-extension", outcome="accepted")
                except Exception as caught:
                    emit_failure_once("broker", "backend", caught)
                    LOG.error("core.parent-control-stage", stage="rollback-extension", outcome="failed")
                    record_exception(caught)
                    rollback_error = rollback_error or caught
                if rollback_error is not None:
                    LOG.critical("core.019", error_type=error_code(rollback_error))
                    failure = RollbackFailure("parent-control rollback could not be verified")
                    emit_backend_failure(failure, original=rollback_error)
                    raise failure from rollback_error
                raise
        except ExecutionPolicyError as error:
            failure = BackendFailure(
                "Could not prepare application blocking rules. Review App Limits: "
                "a wildcard folder may contain an unsupported file or folder name "
                "(such as spaces or commas)."
            )
            emit_backend_failure(failure, original=error)
            LOG.warning("core.parent-control-stage", stage=stage, outcome="failed")
            raise failure from error
        except (OSError, RuntimeError, PreferencesError) as error:
            LOG.warning("core.parent-control-stage", stage=stage, outcome="failed")
            if isinstance(error, (RecoveryPending, RollbackFailure, _GrantAccountInvalidated)):
                raise
            expected = (isinstance(error, ChildExtensionSessionLost) or
                        isinstance(error, BackendFailure) and error.expected)
            failure = BackendFailure("could not change parent-control state", expected=expected)
            emit_backend_failure(failure, original=error)
            raise failure from error

    def revoke_one_time_grant(self, caller_uid: int, target_uid: int) -> None:
        """Remove a live grant and stop the selected child's blocked apps."""
        if not self._acquire_request_lock("revoke"):
            raise Busy("another request is already in progress")
        try:
            LOG.info("core.020")
            config = self._load_config()
            if not self._is_admin(caller_uid):
                raise AccessDenied("administrator access is required")
            target = self._grant_mutation_target(config, target_uid)
            self._withdraw_saved_time(config, target)
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
                public_error = error if isinstance(error, BrokerError) else BackendFailure(
                    "one-time grant could not be revoked")
                emit_backend_failure(public_error, original=error)
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
                    failure = RollbackFailure("one-time grant rollback could not be verified")
                    emit_backend_failure(failure, original=rollback_error)
                    LOG.critical("core.025", error_type=error_code(rollback_error))
                    raise failure from rollback_error
                if public_error is error:
                    raise
                raise public_error from error
        finally:
            self._release_request_lock()

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

    @buffer_saved_time_logs
    def request_deferred_access(self, caller_uid: int, sender: str, target_uid: int,
                                approver_uid: int, duration_seconds: int,
                                allow_soft_blocked_apps: bool, revision: int) -> DeferredApproval:
        correlation_id = str(uuid.uuid4())
        if not self._acquire_request_lock("deferred-approval"):
            raise Busy("another request is already in progress")
        request_kind = "other"
        failure_outcome = "failed"
        result = None
        try:
            config = self._load_config()
            request_kind = self._saved_time_request_kind(config, caller_uid, target_uid)
            self._validate_approval_values(duration_seconds, allow_soft_blocked_apps, deferred=True)
            if type(revision) is not int or not 0 <= revision <= UINT64_MAX:
                raise InvalidRequest("grant record revision is invalid")
            with self._authorizer.watch_deferred(
                request_kind, sender, correlation_id, caller_uid,
            ) as approval:
                if approval.session is None:
                    raise AccessDenied("caller has no eligible local session")
                target, preferences = self._saved_time_target(config, target_uid)
                context = SavedTimeContext(caller_uid, sender, request_kind, target, preferences, approval.session)
                approver = self._approver(config, approver_uid)
                if approver.uid != approver_uid:
                    raise AccessDenied("selected approver identity changed")
                record = self._recover_grant_record_locked(target, revision=revision)
                try:
                    seconds = merged_saved_seconds(record.saved.seconds if record.saved else 0, duration_seconds)
                except ValueError as error:
                    raise InvalidRequest("approval would exceed the saved-time limit") from error

                message = self._approval_message(request_kind, caller_uid, target, duration_seconds,
                                                 allow_soft_blocked_apps, deferred=True)
                outcome = approval.authenticate(target.label, approver.username, message)
                if outcome in {"denied", "cancelled"}:
                    result = DeferredApproval(correlation_id, outcome)
                    return result
                if outcome != "approved":
                    raise BackendFailure("authorizer returned an invalid outcome")
                try:
                    self._resolve_saved_time_session(caller_uid, sender, expected=context.session)
                except AccessDenied:
                    result = DeferredApproval(correlation_id, "cancelled")
                    return result
                if not self._caller_alive(sender):
                    result = DeferredApproval(correlation_id, "cancelled")
                    return result

                def validate_selection():
                    current = self._load_saved_time_record(target)
                    if current != record:
                        raise Stale("grant record changed during authorization")
                    self._recheck_saved_time_selection(self._load_config(), context, current, approver=approver)

                if not approval.admit(validate=validate_selection):
                    result = DeferredApproval(correlation_id, "cancelled")
                    return result
                balance = SavedBalance(seconds, allow_soft_blocked_apps)
                try:
                    saved = self._write_grant_record(record, replace(record, saved=balance))
                except GrantStoreError as error:
                    # Replacement may be visible even if directory sync failed.
                    failure_outcome = "unconfirmed"
                    raise BackendFailure("approved time could not be durably saved") from error
                result = self._finish_deferred_approval(context, saved, correlation_id)
                return result
        finally:
            self._release_request_lock()
            log_saved_time("grant.deferred-approval", surface=request_kind,
                           outcome=result.result_code if result else failure_outcome,
                           saved_seconds=(result.saved_seconds or 0) if result else 0)

    def _finish_deferred_approval(self, context, saved, correlation_id) -> DeferredApproval:
        if saved.fixed is not None and not saved.fixed.ended_by_pause:
            try:
                with self._accounts.bind_grant_mutations(saved.uid, saved.username):
                    paused = self._pause_grant_locked(context, saved)
            except GrantAccountChanged:
                self._reject_invalid_grant(saved)
            except _GrantAccountInvalidated:
                raise
            except _NoPausableTime:
                pass
            except BrokerError as error:
                emit_backend_failure(error)
                pause_error = (error.dbus_name if isinstance(error, (DesktopInUse, RecoveryPending))
                               else BackendFailure.dbus_name)
                return DeferredApproval(correlation_id, "saved_pause_error", pause_error,
                                        saved_seconds=saved.saved.seconds)
            else:
                return DeferredApproval(correlation_id, "saved_paused", saved_seconds=paused.saved.seconds)
        return DeferredApproval(correlation_id, "saved", saved_seconds=saved.saved.seconds)

    @staticmethod
    def _validate_approval_values(duration_seconds, allow_soft_blocked_apps, *, deferred=False):
        if type(duration_seconds) is not int or not (
            MIN_REQUEST_SECONDS <= duration_seconds <= MAX_REQUEST_SECONDS or
            (not deferred and duration_seconds == 0)
        ):
            raise InvalidRequest("duration is outside the supported range")
        if type(allow_soft_blocked_apps) is not bool:
            raise InvalidRequest("allow-soft value must be boolean")

    def _approval_message(self, request_kind, caller_uid, target, duration_seconds,
                          allow_soft_blocked_apps, *, deferred=False) -> str:
        language = (self.get_own_language(caller_uid) if request_kind == "child"
                    else self.get_child_language(caller_uid, target.uid))
        translations = (load_translations(language, (target.desktop_language,))
                        if not language and request_kind == "kiosk" else
                        load_translations(language))
        return format_approval_message(duration_seconds, allow_soft_blocked_apps, translations,
                                       deferred=deferred)

    def _request_access(self, request_kind: str, caller_uid: int, sender: str,
                        target_uid: int, approver_uid: int,
                        duration_seconds: int,
                        allow_soft_blocked_apps: bool) -> tuple[str, str, int]:
        correlation_id = str(uuid.uuid4())
        if not self._acquire_request_lock("approval"):
            raise Busy("another request is already in progress")
        authorization_scope = ExitStack()
        try:
            config = self._load_config()
            if request_kind == "kiosk":
                self._check_caller(config, caller_uid)
            elif request_kind != "child":
                raise BackendFailure("request kind is invalid")
            self._validate_approval_values(duration_seconds, allow_soft_blocked_apps)
            target = self._grant_mutation_target(config, target_uid)
            if request_kind == "child" and caller_uid != target.uid:
                raise AccessDenied("a child can request access only for itself")
            approver = self._approver(config, approver_uid)
            preferences = self._load_request_preferences(target.uid)
            if request_kind == "child" and not preferences["parent_control_enabled"]:
                raise AccessDenied("parent control is not enabled for this account")
            try:
                record = self._recover_grant_record_locked(target)
            except RecoveryPending as error:
                # The existing immediate methods already expose Busy while a
                # transfer is pending. Keep that response for older clients.
                raise Busy("a saved-time transfer is awaiting recovery") from error
            LOG.info(
                "core.026",
                request=correlation_id,
                duration_seconds=duration_seconds,
                allow_soft=allow_soft_blocked_apps,
                kind=request_kind,
            )

            message = self._approval_message(request_kind, caller_uid, target, duration_seconds,
                                             allow_soft_blocked_apps)
            approval = authorization_scope.enter_context(self._authorizer.check(
                request_kind, sender, correlation_id, target.label, approver.username, message,
            ))
            outcome = approval.outcome
            if outcome not in {"approved", "denied", "cancelled"}:
                raise BackendFailure("authorizer returned an invalid outcome")
            if outcome != "approved":
                LOG.info("core.027", request=correlation_id, outcome=outcome)
                return correlation_id, outcome, 0
            if not self._caller_alive(sender):
                LOG.info("core.027", request=correlation_id, outcome="cancelled")
                return correlation_id, "cancelled", 0
            # Fail closed if the selected account changed while the parent was
            # authenticating (including an AccountType promotion to admin), or
            # if the selected approver is no longer an eligible administrator.
            if self._check_grant_account(config, target, record=record) != target:
                raise AccessDenied("selected account changed during authorization")
            if self._approver(config, approver_uid) != approver:
                raise AccessDenied("selected approver changed during authorization")
            if self._load_request_preferences(target.uid) != preferences:
                raise AccessDenied("preferences changed during authorization")

            replaced = None  # A rest-of-day grant is never fixed.
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
                    LOG.info("core.027", request=correlation_id, outcome="cancelled")
                    return correlation_id, "cancelled", 0
                if self._check_grant_account(config, target, record=record) != target:
                    raise AccessDenied("selected account changed during authorization")
                if self._approver(config, approver_uid) != approver:
                    raise AccessDenied("selected approver changed during authorization")
                if self._load_request_preferences(target.uid) != preferences:
                    raise AccessDenied("preferences changed during authorization")

                try:
                    native_deadline = (self._native_deadline(target.uid, preferences)
                                       if request_kind == "child" else None)
                    grant_time, grant_duration = self._accounts.get_extension(target.uid)
                except NativeDeadlineSuspended:
                    LOG.info("core.027", request=correlation_id, outcome="cancelled")
                    return correlation_id, "cancelled", 0
                except Exception as error:
                    raise BackendFailure("remaining-time status is unavailable") from error
                issued_at_time = self._now()
                self._observe_grant(target.uid, grant_time, grant_duration)
                status = self._time_status_from_usage(
                    preferences, usage_entries, grant_time, grant_duration,
                    duration_seconds, issued_at_time, native_deadline=native_deadline,
                )
                duration = status.calculated_active_extension_seconds
                replaced = ((grant_time, grant_duration), status)
                LOG.info("core.grant-calculation", request=correlation_id,
                         daily=status.daily_allowance_remaining_seconds,
                         grant=status.one_time_grant_remaining_seconds,
                         additional=duration_seconds, calculated=duration)

            # The identity-scoped query may take up to the backend timeout.
            # Revalidate again immediately before privileged account writes.
            if not self._caller_alive(sender):
                LOG.info("core.027", request=correlation_id, outcome="cancelled")
                return correlation_id, "cancelled", 0
            if self._check_grant_account(config, target, record=record) != target:
                raise AccessDenied("selected account changed during authorization")
            if self._approver(config, approver_uid) != approver:
                raise AccessDenied("selected approver changed during authorization")
            if self._load_request_preferences(target.uid) != preferences:
                raise AccessDenied("preferences changed during request")
            issued_at = int(issued_at_time.timestamp())
            if not 0 < issued_at <= UINT64_MAX or not 0 < duration <= UINT32_MAX:
                raise BackendFailure("calculated extension is outside the supported range")
            grant = (issued_at, duration)
            desired_filter, termination_patterns = self._approval_app_policy(
                target.uid, preferences, allow_soft_blocked_apps,
            )

            cleared_record = None

            def admit_effect():
                nonlocal cleared_record
                if record is not None:
                    current = self._load_saved_time_record(target)
                    if current.intent is not None:
                        raise Busy("a saved-time transfer is awaiting recovery")
                    if current != record:
                        raise BackendFailure("saved-time record changed during request")
                # Preflight and snapshot reads may block. Revalidate the
                # original selection after those reads, then let the authorizer
                # observe queued departure events and claim the sole boundary.
                if not self._caller_alive(sender):
                    return False
                if self._check_grant_account(config, target, record=record) != target:
                    raise AccessDenied("selected account changed during request")
                if self._approver(config, approver_uid) != approver:
                    raise AccessDenied("selected approver changed during request")
                if self._load_request_preferences(target.uid) != preferences:
                    raise AccessDenied("preferences changed during request")
                if record is not None and self._grant_is_fenced(record):
                    self._reject_invalid_grant(record)
                if not approval.admit():
                    return False
                if record is not None and record.fixed is not None and record.fixed.grant == grant:
                    # If the new grant has the same tuple, a crash could
                    # otherwise make it inherit the previous fixed marker.
                    cleared_record = replace(record, fixed=None)
                    cleared_record = self._write_grant_record(record, cleared_record)
                return True

            try:
                applied = self._apply(
                    target.uid, preferences, desired_filter, grant, correlation_id,
                    termination_patterns,
                    admit=admit_effect,
                    activate_child_extension=(request_kind == "kiosk" and
                                              preferences["parent_control_enabled"]),
                )
            except BrokerError as error:
                if cleared_record is not None and not isinstance(error, RollbackFailure):
                    self._restore_immediate_tracking(config, target, record)
                raise
            if not applied:
                LOG.info("core.027", request=correlation_id, outcome="cancelled")
                return correlation_id, "cancelled", 0
            LOG.info("core.032", request=correlation_id)
            self._track_immediate_grant(config, target, correlation_id, grant,
                                        allow_soft_blocked_apps, replaced, record, cleared_record)
            return correlation_id, "approved", duration
        finally:
            try:
                authorization_scope.close()
            finally:
                self._release_request_lock()

    def _check_grant_account(self, config: Configuration, target: UserAccount, *,
                             record: GrantRecord | None = None) -> UserAccount:
        if record is not None:
            return self._check_record_account(record, config=config)
        current = self._target(config, target.uid)
        if current.username != target.username:
            raise AccessDenied("selected account changed during request")
        return current

    def _restore_immediate_tracking(self, config: Configuration, target: UserAccount,
                                    record: GrantRecord) -> None:
        try:
            current = self._grant_store.load(target.uid, target.username)
            self._check_record_account(current, config=config)
            cleared = replace(record, revision=record.revision + 1, fixed=None)
            # A failed directory sync can leave the marker clear published.
            if current == cleared:
                self._write_grant_record(current, replace(record, revision=current.revision))
        except (BrokerError, GrantStoreError) as error:
            record_exception(error)

    def _track_immediate_grant(
            self, config: Configuration, target: UserAccount, correlation_id: str, grant: GrantTuple,
            allow_soft_blocked_apps: bool, replaced: tuple[GrantTuple, TimeStatus] | None,
            record: GrantRecord | None, cleared_record: GrantRecord | None) -> None:
        """Persist the verified result without changing the saved balance."""
        if record is None:
            return
        try:
            current = cleared_record or record
            self._check_record_account(current, config=config)
            fixed = None
            if replaced is not None:
                live, status = replaced
                if new_grant_is_fixed(record, live, status.daily_allowance_remaining_seconds,
                                      status.one_time_grant_remaining_seconds):
                    fixed = FixedGrant(grant, allow_soft_blocked_apps)
            self._write_grant_record(current, replace(current, fixed=fixed))
        except (BrokerError, GrantStoreError) as error:
            # The account grant has committed and cannot inherit an old marker.
            record_exception(error)
            LOG.warning("core.grant-tracking", request=correlation_id, outcome="failed")
        else:
            LOG.info("core.grant-tracking", request=correlation_id,
                     outcome="deadline" if fixed is None else "fixed")

    def _load_config(self) -> Configuration:
        try:
            return self._config_loader()
        except ConfigurationError as error:
            LOG.error("core.033", error_type=error_code(error))
            raise BackendFailure("broker configuration is unavailable") from error

    def _load_request_preferences(self, target_uid: int) -> dict:
        if self._preferences is None:
            raise BackendFailure("preferences are unavailable")
        try:
            # Presentation changes cannot invalidate an in-flight approval.
            return {key: value for key, value in self._preferences.load(target_uid).items()
                    if key != "personal"}
        except (OSError, PreferencesError) as error:
            raise BackendFailure("preferences are unavailable") from error

    def _approval_app_policy(self, uid: int, preferences: dict, allow_soft: bool
                             ) -> tuple[tuple[bool, tuple[str, ...]], tuple[str, ...] | None]:
        desired_filter = (False, blocked_targets(preferences, allow_soft))
        patterns = () if allow_soft else blocked_patterns(preferences, False)
        if allow_soft or not (desired_filter[1] or patterns):
            return desired_filter, None
        if self._running_apps is None:
            raise BackendFailure("blocked application termination is unavailable")
        try:
            self._running_apps.preflight(uid, desired_filter[1], patterns)
        except GrantAccountChanged:
            raise
        except Exception as error:
            raise BackendFailure("blocked applications could not be stopped") from error
        return desired_filter, patterns

    def _set_verified_filter(self, uid: int, desired_filter: tuple[bool, tuple[str, ...]]) -> None:
        # The adapter reconciles execution rules after setting the account
        # property. Even a matching property needs a retry after a failure.
        self._accounts.set_filter(uid, desired_filter)
        if self._accounts.get_filter(uid) != desired_filter:
            raise BackendFailure("app-filter verification failed")

    def _terminate_approval_apps(self, uid: int, targets: tuple[str, ...],
                                 patterns: tuple[str, ...], correlation_id: str,
                                 *, redeem: _RedeemAttempt | None = None,
                                 expected: tuple[GrantTuple, ...] = ()) -> int:
        LOG.info("core.036", request=correlation_id)
        if redeem is not None:
            self._require_redeem_live(redeem, *expected)
            if not self._redeem_current(redeem.intent):
                return 0
            self._write_redeem_intent(redeem, replace(redeem.intent, termination_started=True))
            self._require_redeem_live(redeem, *expected)
            if not self._redeem_current(redeem.intent):
                return 0
            prior_termination = redeem.termination_may_have_changed_processes
            redeem.termination_may_have_changed_processes = True
        terminated = self._running_apps.terminate(uid, targets, patterns)
        if type(terminated) is not int or terminated < 0:
            raise BackendFailure("blocked application termination failed")
        if redeem is not None:
            redeem.termination_may_have_changed_processes = prior_termination or terminated > 0
        LOG.info("core.037", request=correlation_id, count=terminated)
        return terminated

    def _check_record_account(self, record: GrantRecord, *, config: Configuration | None = None) -> UserAccount:
        if self._grant_is_fenced(record):
            self._reject_invalid_grant(record)
        target = self._target(
            config if config is not None else self._load_config(), record.uid,
            on_invalid=lambda: self._reject_invalid_grant(record),
        )
        if target.username != record.username or self._grant_is_fenced(record):
            self._reject_invalid_grant(record)
        return target

    def _redeem_preferences(self, record: GrantRecord) -> dict:
        self._check_record_account(record)
        preferences = self._load_request_preferences(record.uid)
        if not preferences["parent_control_enabled"]:
            raise AccessDenied("parent control is not enabled for this account")
        return preferences

    def _recover_redeem_intent(self, record: GrantRecord) -> GrantRecord:
        """Resolve one child's durable redemption under the transaction lock."""
        assert isinstance(record.intent, RedeemIntent)
        attempt = _RedeemAttempt(record, record.intent,
                                 termination_may_have_changed_processes=record.intent.termination_started)
        with self._accounts.bind_grant_mutations(record.uid, record.username):
            result, _ = self._resolve_redeem_intent(attempt, str(uuid.uuid4()))
        return result

    def _resolve_redeem_intent(self, attempt: _RedeemAttempt,
                               correlation_id: str) -> tuple[GrantRecord, bool]:
        with _report_grant_recovery("redemption"):
            result, committed = self._roll_forward_redeem_intent(attempt, correlation_id)
        log_saved_time("grant.recovery", stage="redemption",
                       outcome="committed" if committed else "superseded")
        return result, committed

    def _roll_forward_redeem_intent(self, attempt: _RedeemAttempt,
                                   correlation_id: str) -> tuple[GrantRecord, bool]:
        uid = attempt.record.uid
        intent = attempt.intent

        try:
            preferences = self._redeem_preferences(attempt.record)

            def read_live():
                try:
                    return self._read_redeem_live(attempt)
                except BackendFailure:
                    # Publication is unknown. Close any temporary bridge and
                    # enforce full app policy until the live grant is readable.
                    repair_filter = True
                    try:
                        self._reconcile_redeem_time_state(
                            attempt.record, preferences, destination=None,
                        )
                    except (GrantAccountChanged, _GrantAccountInvalidated):
                        repair_filter = False
                        raise
                    finally:
                        if repair_filter:
                            self._set_redeem_strict_filter(attempt.record, preferences)
                    raise

            if attempt.original_filter is None:
                # An earlier replacement can be visible even when its
                # directory sync failed. Confirm durability before replay.
                try:
                    self._write_redeem_intent(attempt, attempt.intent)
                except RecoveryPending:
                    # An observed full-day bridge still needs to be removed.
                    try:
                        live = self._read_redeem_live(attempt)
                    except BackendFailure:
                        live = None
                    self._reconcile_redeem_time_state(
                        attempt.record, preferences,
                        destination=None if live is None else live == intent.destination,
                        bridge_only=True,
                    )
                    raise
            live = read_live()
            if live == intent.source:
                # An interrupted attempt may have left the full-day bridge
                # active. Restore bounded time before app preflight can fail.
                self._reconcile_redeem_time_state(attempt.record, preferences, destination=False)
                if attempt.original_filter is None:
                    # After a restart the current filter may be the one the
                    # interrupted attempt installed before writing the grant.
                    self._set_redeem_strict_filter(attempt.record, preferences)
                desired_filter, patterns = self._redeem_app_policy(attempt, preferences)

                def recheck():
                    if self._redeem_preferences(attempt.record) != preferences:
                        raise AccessDenied("preferences changed during redemption recovery")
                    return True

                try:
                    self._apply(uid, preferences, desired_filter, intent.destination,
                                correlation_id, patterns, admit=recheck, redeem=attempt,
                                activate_child_extension=intent.activate_child_extension)
                except _GrantAccountInvalidated:
                    raise
                except BrokerError:
                    live = read_live()
                    if live == intent.source:
                        raise
                else:
                    return self._finish_redeem_intent(attempt.record, committed=True), True

            if live == intent.destination:
                try:
                    self._repair_redeem_destination(attempt, correlation_id)
                except GrantAccountChanged:
                    self._reject_invalid_grant(attempt.record)
                except _GrantAccountInvalidated:
                    raise
                except Exception:
                    live = read_live()
                    if live in (intent.source, intent.destination):
                        if not self._redeem_current(intent):
                            self._set_redeem_strict_filter(
                                attempt.record, self._redeem_preferences(attempt.record),
                            )
                        raise
                else:
                    return self._finish_redeem_intent(attempt.record, committed=True), True

            preferences = self._redeem_preferences(attempt.record)
            self._reconcile_redeem_time_state(attempt.record, preferences, destination=False)
            self._set_redeem_strict_filter(attempt.record, preferences)
            return self._finish_redeem_intent(attempt.record, committed=False), False
        except GrantAccountChanged:
            self._reject_invalid_grant(attempt.record)
        except (RecoveryPending, RollbackFailure, _GrantAccountInvalidated):
            raise
        except Exception as error:
            raise RecoveryPending("saved-time redemption could not be resolved") from error

    def _finish_redeem_intent(self, record: GrantRecord, *, committed: bool) -> GrantRecord:
        intent = record.intent
        assert isinstance(intent, RedeemIntent)
        fixed = None
        if committed and intent.record_fixed:
            fixed = FixedGrant(intent.destination, intent.allow_soft_blocked_apps)
        if not committed:
            try:
                self._redeem_preferences(record)
            except _GrantAccountInvalidated:
                raise
            except BrokerError as error:
                raise RecoveryPending("redemption account could not be revalidated") from error
        try:
            return self._write_grant_record(record, replace(record, fixed=fixed, saved=None, intent=None))
        except GrantStoreError as error:
            raise RecoveryPending("redemption result durability is uncertain") from error

    def _read_redeem_live(self, attempt: _RedeemAttempt) -> GrantTuple:
        self._check_record_account(attempt.record)
        if attempt.external is not None:
            return attempt.external
        try:
            live = self._read_live_grant(attempt.record.uid)
        except GrantAccountChanged:
            self._reject_invalid_grant(attempt.record)
        if live not in (attempt.intent.source, attempt.intent.destination):
            attempt.external = live
        return live

    def _require_redeem_live(self, attempt: _RedeemAttempt, *expected: GrantTuple) -> None:
        if self._read_redeem_live(attempt) not in expected:
            raise BackendFailure("the live grant changed during redemption")
        self._check_record_account(attempt.record)

    def _redeem_current(self, intent: RedeemIntent) -> bool:
        return self._now().timestamp() < sum(intent.destination)

    def _redeem_app_policy(self, attempt: _RedeemAttempt, preferences: dict
                           ) -> tuple[tuple[bool, tuple[str, ...]], tuple[str, ...] | None]:
        if self._redeem_current(attempt.intent):
            return self._approval_app_policy(
                attempt.record.uid, preferences, attempt.intent.allow_soft_blocked_apps,
            )
        return (False, blocked_targets(preferences, False)), None

    def _write_redeem_intent(self, attempt: _RedeemAttempt, intent: RedeemIntent) -> None:
        record = attempt.record
        self._check_record_account(record)
        try:
            attempt.record = self._write_grant_record(record, replace(record, intent=intent))
        except GrantStoreError as error:
            try:
                observed = self._grant_store.load(record.uid, record.username)
            except GrantStoreError:
                raise RecoveryPending("redemption intent durability is uncertain") from error
            if record.intent is None and observed == record:
                raise BackendFailure("redemption intent could not be stored") from error
            if record.intent is not None and observed == replace(record, revision=record.revision + 1,
                                                                 intent=intent):
                # A failed sync can leave a new revision visible. A later
                # source retry must still publish it durably before effects.
                attempt.record = observed
                attempt.intent = intent
            raise RecoveryPending("redemption intent durability is uncertain") from error
        attempt.intent = intent

    def _write_redeem_extension(self, attempt: _RedeemAttempt) -> None:
        intent = attempt.intent
        live = self._read_redeem_live(attempt)
        if live == intent.source:
            self._check_record_account(attempt.record)
            try:
                self._write_extension(attempt.record.uid, intent.destination,
                                      readback=lambda: self._read_redeem_live(attempt))
            except GrantAccountChanged:
                self._reject_invalid_grant(attempt.record)
            except _GrantAccountInvalidated:
                raise
            except Exception:
                # A dispatched write can land even when Set or read-back fails.
                # Preserve the destination if observed and finish the other effects.
                if self._read_redeem_live(attempt) != intent.destination:
                    raise
        elif live != intent.destination:
            raise BackendFailure("the live grant changed during redemption")

    def _reconcile_redeem_time_state(self, record: GrantRecord, preferences: dict, *,
                                    destination: bool | None, bridge_only: bool = False) -> None:
        transfer = record.bridge_repair or record.intent
        state = transfer.time_state
        if state is None:
            return
        uid = record.uid
        bridge_only = bridge_only or destination is None

        # An unacknowledged Set can still publish the grant. Keep configured
        # daily enforcement when the bridge started with disabled limits.
        limit_type = state.limit_type or DAILY_LIMIT_FLAG
        configured_daily = preferences["daily_time_limit_minutes"] * 60

        # Recovery leaves ActiveExtension alone. Close the temporary schedule
        # first and retain any daily enforcement while repairing the cap.
        schedule = self._accounts.get_daily_schedule(uid)
        if schedule != state.daily_schedule and (not bridge_only or schedule == FULL_DAY_SCHEDULE):
            self._check_record_account(record)
            self._accounts.set_daily_schedule(uid, state.daily_schedule)
            if self._accounts.get_daily_schedule(uid) != state.daily_schedule:
                raise BackendFailure("daily-schedule recovery verification failed")
        current_type = self._accounts.get_limit_type(uid)
        if current_type != limit_type and (not bridge_only or current_type == DAILY_SCHEDULE_FLAG):
            self._check_record_account(record)
            self._accounts.set_limit_type(uid, limit_type)
            if self._accounts.get_limit_type(uid) != limit_type:
                raise BackendFailure("limit-type recovery verification failed")
        # With native limits still off, the bridge never changed the cap.
        if bridge_only and current_type == 0:
            return
        # With a preexisting limit, an unknown publication can leave two
        # plausible caps. When the bridge enabled limits, both paths use the
        # configured daily cap.
        if (destination is None and record.bridge_repair is None and state.limit_type and
                state.daily_limit != configured_daily):
            return
        current_daily = self._accounts.get_daily_limit(uid)
        # Either recorded cap can survive partial cleanup. Leave unrelated
        # native edits alone during bridge-only repair.
        if bridge_only and current_daily not in (state.daily_limit, configured_daily):
            return
        if destination is None and state.limit_type and state.daily_limit != configured_daily:
            destination = self._read_live_grant(uid) == transfer.destination
        daily_limit = configured_daily if destination or not state.limit_type else state.daily_limit
        if current_daily != daily_limit:
            self._check_record_account(record)
            self._accounts.set_daily_limit(uid, daily_limit)
            if self._accounts.get_daily_limit(uid) != daily_limit:
                raise BackendFailure("daily-limit recovery verification failed")

    def _set_redeem_strict_filter(self, record: GrantRecord, preferences: dict) -> None:
        self._check_record_account(record)
        self._set_verified_filter(record.uid, (False, blocked_targets(preferences, False)))

    def _repair_redeem_destination(self, attempt: _RedeemAttempt, correlation_id: str) -> None:
        intent = attempt.intent
        record = attempt.record
        preferences = self._redeem_preferences(record)
        self._require_redeem_live(attempt, intent.destination)
        self._reconcile_redeem_time_state(record, preferences, destination=True)
        desired_filter, patterns = self._redeem_app_policy(attempt, preferences)
        if self._redeem_preferences(record) != preferences:
            raise AccessDenied("preferences changed during redemption recovery")
        self._require_redeem_live(attempt, intent.destination)
        applied_filter = None
        if self._redeem_current(intent):
            self._set_verified_filter(record.uid, desired_filter)
            applied_filter = desired_filter
            if patterns is not None:
                self._terminate_approval_apps(record.uid, desired_filter[1], patterns, correlation_id,
                                              redeem=attempt, expected=(intent.destination,))
        self._complete_redeem_effects(attempt, applied_filter)

    def _complete_redeem_effects(
            self, attempt: _RedeemAttempt,
            applied_filter: tuple[bool, tuple[str, ...]] | None,
    ) -> None:
        intent = attempt.intent
        self._require_redeem_live(attempt, intent.destination)
        if intent.activate_child_extension and self._redeem_current(intent):
            if self._extensions is None:
                raise BackendFailure("extension management is unavailable")
            self._extensions.set_enabled(attempt.record.uid, True, recover_global_switch=True)
            self._require_redeem_live(attempt, intent.destination)
        preferences = self._redeem_preferences(attempt.record)
        if not self._redeem_current(intent):
            strict_filter = False, blocked_targets(preferences, False)
            if applied_filter != strict_filter:
                self._set_redeem_strict_filter(attempt.record, preferences)
        # Validate eligibility before the final live read. A replacement
        # during that validation must still enter tuple recovery.
        if self._read_redeem_live(attempt) != intent.destination:
            raise BackendFailure("the live grant changed before redemption committed")

    def _restore_redeem_attempt(self, attempt: _RedeemAttempt) -> None:
        record = attempt.record
        intent = attempt.intent
        preferences = self._redeem_preferences(record)
        try:
            live = self._read_redeem_live(attempt)
        except BackendFailure:
            # A time read failure leaves publication uncertain. Remove the
            # bridge and keep full app policy until recovery verifies the tuple.
            live = None
        destination = None if live is None else live == intent.destination
        repair_filter = True
        try:
            self._reconcile_redeem_time_state(record, preferences, destination=destination)
        except (GrantAccountChanged, _GrantAccountInvalidated):
            repair_filter = False
            raise
        finally:
            current = self._redeem_current(intent)
            if repair_filter and (not current or not destination):
                if (live == intent.source and current and
                        not attempt.termination_may_have_changed_processes and
                        attempt.original_filter is not None):
                    self._check_record_account(record)
                    self._set_verified_filter(record.uid, attempt.original_filter)
                else:
                    self._set_redeem_strict_filter(record, preferences)

    def _apply(self, target_uid: int,
               preferences: dict, desired_filter: tuple[bool, tuple[str, ...]],
               extension: tuple[int, int], correlation_id: str,
               termination_patterns: tuple[str, ...] | None = None,
               *, admit: Callable[[], bool],
               activate_child_extension: bool = False,
               redeem: _RedeemAttempt | None = None) -> bool:
        old_limit_type = old_daily_limit = old_daily_schedule = old_filter = old_extension = None
        snapshot_complete = False
        termination_may_have_changed_processes = False

        def check_account():
            if redeem is not None:
                self._check_record_account(redeem.record)

        try:
            if (activate_child_extension and self._extensions is None and
                    (redeem is None or self._redeem_current(redeem.intent))):
                raise BackendFailure("extension management is unavailable")
            # Capture every reversible value before the first write. A read
            # failure here has made no state change, so it needs public error
            # translation but must not attempt a partial rollback.
            old_limit_type = self._accounts.get_limit_type(target_uid)
            old_daily_limit = self._accounts.get_daily_limit(target_uid)
            old_daily_schedule = self._accounts.get_daily_schedule(target_uid)
            old_filter = self._accounts.get_filter(target_uid)
            if redeem is None:
                old_extension = self._accounts.get_extension(target_uid)
            elif self._read_redeem_live(redeem) != redeem.intent.source:
                raise Stale("grant changed while preparing the redemption")
            desired_daily_limit = preferences["daily_time_limit_minutes"] * 60
            # Cancellation or validation failure before admission made no
            # changes. In particular, it must not trigger rollback writes.
            if not admit():
                return False
            initialize_time = old_limit_type == 0 or old_daily_limit != desired_daily_limit
            if redeem is not None:
                if self._read_redeem_live(redeem) != redeem.intent.source:
                    raise Stale("grant changed while preparing the redemption")
                if redeem.record.intent is None:
                    redeem.original_filter = old_filter
                time_state = redeem.intent.time_state
                if time_state is None and initialize_time:
                    time_state = RedeemTimeState(old_limit_type, old_daily_limit, old_daily_schedule)
                if time_state is not None:
                    initialize_time = True
                    old_limit_type = time_state.limit_type
                    old_daily_schedule = time_state.daily_schedule
                # Rewrite even an existing intent before new effects. An
                # earlier failure may have published it without syncing it.
                self._write_redeem_intent(redeem, replace(redeem.intent, time_state=time_state))
                self._require_redeem_live(redeem, redeem.intent.source)
            snapshot_complete = True
            if initialize_time:
                LOG.info("core.034", request=correlation_id)
                self._prepare_time_state(
                    target_uid, old_limit_type or DAILY_LIMIT_FLAG, desired_daily_limit,
                    check_account=check_account,
                )
            if redeem is not None:
                self._require_redeem_live(redeem, redeem.intent.source, extension)
                if not self._redeem_current(redeem.intent):
                    desired_filter = False, blocked_targets(preferences, False)
                    termination_patterns = None
            LOG.info("core.035", request=correlation_id)
            self._set_verified_filter(target_uid, desired_filter)
            if termination_patterns is not None:
                termination_may_have_changed_processes = True
                terminated = self._terminate_approval_apps(
                    target_uid, desired_filter[1], termination_patterns, correlation_id, redeem=redeem,
                    expected=() if redeem is None else (redeem.intent.source, extension),
                )
                termination_may_have_changed_processes = terminated > 0
            LOG.info("core.038", request=correlation_id)
            if redeem is not None:
                self._write_redeem_extension(redeem)
                self._require_redeem_live(redeem, extension)
                if initialize_time:
                    self._finalize_time_state(
                        target_uid, old_limit_type or DAILY_LIMIT_FLAG, old_daily_schedule,
                        check_account=check_account,
                    )
                self._complete_redeem_effects(redeem, desired_filter)
            else:
                if initialize_time:
                    self._finish_time_state(
                        target_uid, old_limit_type or DAILY_LIMIT_FLAG, old_daily_schedule, extension,
                    )
                else:
                    self._write_extension(target_uid, extension)
                if self._accounts.get_extension(target_uid) != extension:
                    raise BackendFailure("extension verification failed")
                # Activation follows the verified grant so it cannot enforce
                # the old exhausted balance.
                if activate_child_extension:
                    self._extensions.set_enabled(target_uid, True, recover_global_switch=True)
            self._observe_grant(target_uid, *extension)
            return True
        except Exception as error:
            if isinstance(error, GrantAccountChanged) and redeem is not None:
                self._reject_invalid_grant(redeem.record)
            if isinstance(error, _GrantAccountInvalidated):
                raise
            public_error = error if isinstance(error, BrokerError) else BackendFailure(
                "account update failed", expected=isinstance(error, ChildExtensionSessionLost))
            emit_backend_failure(public_error, original=error)
            # Preserve the primary failure even if rollback raises a different
            # error with an explicit cause that hides the original context.
            record_exception(error)
            if not snapshot_complete:
                LOG.warning("core.039", request=correlation_id, error_type=error_code(error))
            elif redeem is not None:
                try:
                    self._restore_redeem_attempt(redeem)
                except GrantAccountChanged:
                    self._reject_invalid_grant(redeem.record)
                except _GrantAccountInvalidated:
                    raise
                except Exception as rollback_error:
                    failure = RollbackFailure("redemption rollback could not be verified")
                    emit_backend_failure(failure, original=rollback_error)
                    LOG.critical("core.041", request=correlation_id)
                    raise failure from rollback_error
            elif termination_may_have_changed_processes:
                # A killed process cannot be restored. Keep the canonical
                # hard+soft block filter active and restore the time state.
                self._restore_after_termination(
                    target_uid, old_limit_type, old_daily_limit, desired_filter,
                    old_extension, old_daily_schedule, correlation_id,
                )
            else:
                self._restore(
                    target_uid, old_limit_type, old_daily_limit, old_filter,
                    old_extension, old_daily_schedule, correlation_id,
                )
            if public_error is error:
                raise
            raise public_error from error

    def _restore_after_termination(
            self, target_uid: int, old_limit_type: int, old_daily_limit: int,
            desired_filter, old_extension, old_daily_schedule, correlation_id: str) -> None:
        try:
            LOG.warning("core.040", request=correlation_id)
            self._write_time_state(
                target_uid, old_limit_type, old_daily_limit, old_daily_schedule, old_extension,
            )
            self._accounts.set_filter(target_uid, desired_filter)
            if (self._accounts.get_extension(target_uid) != old_extension or
                    self._accounts.get_filter(target_uid) != desired_filter or
                    self._accounts.get_limit_type(target_uid) != old_limit_type or
                    self._accounts.get_daily_limit(target_uid) != old_daily_limit or
                    self._accounts.get_daily_schedule(target_uid) != old_daily_schedule):
                raise RuntimeError("post-termination rollback read-back mismatch")
        except Exception as error:
            failure = RollbackFailure("account rollback after app termination could not be verified")
            emit_backend_failure(failure, original=error)
            LOG.critical("core.041", request=correlation_id)
            raise failure from error

    def _restore(self, target_uid: int, old_limit_type: int, old_daily_limit: int,
                 old_filter, old_extension, old_daily_schedule,
                 correlation_id: str | None) -> None:
        try:
            if correlation_id is None:
                LOG.warning("core.parent-control-rollback")
            else:
                LOG.warning("core.042", request=correlation_id)
            self._write_time_state(
                target_uid, old_limit_type, old_daily_limit, old_daily_schedule, old_extension,
            )
            self._accounts.set_filter(target_uid, old_filter)
            if (self._accounts.get_extension(target_uid) != old_extension or
                    self._accounts.get_filter(target_uid) != old_filter or
                    self._accounts.get_limit_type(target_uid) != old_limit_type or
                    self._accounts.get_daily_limit(target_uid) != old_daily_limit or
                    self._accounts.get_daily_schedule(target_uid) != old_daily_schedule):
                raise RuntimeError("rollback read-back mismatch")
        except Exception as error:
            failure = RollbackFailure("account rollback could not be verified")
            emit_backend_failure(failure, original=error)
            if correlation_id is None:
                LOG.critical("core.parent-control-rollback-failed")
            else:
                LOG.critical("core.041", request=correlation_id)
            raise failure from error
