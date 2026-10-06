"""Root-owned child policy and personal language with validated atomic writes."""

from __future__ import annotations

import json
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
import math
import os
import re
import tempfile
from dataclasses import dataclass, field
import threading
from pathlib import Path

from .config import UINT32_MAX, validate_target

FORMAT_VERSION = 4
VALID_APP_STATES = {"allowed", "permanent", "conditional"}
MIN_DAILY_LIMIT_MINUTES = 0
MAX_DAILY_LIMIT_MINUTES = 24 * 60
MIN_CUSTOM_MINUTES = 0.1
MAX_CUSTOM_MINUTES = 1440
VALID_DURATIONS = {"custom", "0", "300", "900", "1800", "3600", "7200", "14400"}
DESKTOP_ID_RE = re.compile(r"^[^/\x00]+\.desktop$")
_UNSAFE_PATTERN_CHARACTERS = frozenset(",\"\\\x00\r\n")
REQUIRED_REQUEST_KEYS = {
    "last_selected_duration", "last_custom_minutes", "allow_soft_blocked_apps",
}
OPTIONAL_REQUEST_KEYS = {
    "last_selected_approver_uid", "kiosk_muted", "child_muted",
}
LOG = get_logger("preferences")


class PreferencesError(ValueError):
    """A preference record is malformed or could not be stored safely."""


LANGUAGE_RE = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*")
REMINDER_ID_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
MAX_REMINDERS = 64
MAX_REMINDER_TEXT = 4096


def default_notifications() -> dict:
    """Fresh defaults; an explicitly saved empty list disables reminders."""
    return {"show_in_fullscreen": True, "reminders": [
        {"id": identifier, "value": value, "unit": unit, "text": ""}
        for identifier, value, unit in (
            ("ten-minutes", 10, "minute"), ("five-minutes", 5, "minute"),
            ("one-minute", 1, "minute"), ("fifteen-seconds", 15, "second"))
    ]}


def validate_notifications(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != {"show_in_fullscreen", "reminders"}:
        raise PreferencesError("invalid notification preferences")
    if type(raw["show_in_fullscreen"]) is not bool:
        raise PreferencesError("fullscreen notification state must be boolean")
    records = raw["reminders"]
    if not isinstance(records, list) or len(records) > MAX_REMINDERS:
        raise PreferencesError("notifications must be an array of at most 64 reminders")
    reminders, ids = [], set()
    for record in records:
        if (not isinstance(record, dict) or not {"id", "value", "unit"} <= set(record) or
                not set(record) <= {"id", "value", "unit", "text"}):
            raise PreferencesError("invalid reminder record")
        identifier, value, unit = (record[key] for key in ("id", "value", "unit"))
        text = record.get("text", "")
        if (not isinstance(identifier, str) or len(identifier) > 64 or
                not REMINDER_ID_RE.fullmatch(identifier) or identifier in ids):
            raise PreferencesError("invalid or duplicate reminder ID")
        if not isinstance(unit, str) or unit not in {"minute", "second"}:
            raise PreferencesError("invalid reminder unit")
        maximum = UINT32_MAX // 60 if unit == "minute" else UINT32_MAX
        if type(value) is not int or not 1 <= value <= maximum:
            raise PreferencesError("reminder time must be a positive whole uint32 duration in seconds")
        if (not isinstance(text, str) or len(text) > MAX_REMINDER_TEXT or "\x00" in text or
                any(0xD800 <= ord(char) <= 0xDFFF for char in text)):
            raise PreferencesError("invalid reminder text")
        ids.add(identifier)
        # Preserve literal custom text. Whitespace-only content means default.
        reminders.append({"id": identifier, "value": value, "unit": unit,
                          "text": text if text.strip() else ""})
    return {"show_in_fullscreen": raw["show_in_fullscreen"], "reminders": reminders}


def validate_language(value: object) -> str:
    """Validate a portable language ID; empty means follow the session locale.

    This stores intent, independently of which translations are installed.
    Locale environment strings, paths and gettext search lists are not IDs.
    """
    if not isinstance(value, str) or len(value) > 63 or (
            value and not LANGUAGE_RE.fullmatch(value)):
        raise PreferencesError("language must be empty or a hyphen-separated language ID")
    return value


def default_preferences() -> dict:
    return {
        "version": FORMAT_VERSION,
        "personal": {"language": "", "notifications": default_notifications()},
        "parent_control_enabled": False,
        "daily_time_limit_minutes": MIN_DAILY_LIMIT_MINUTES,
        "apps": {},
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": MIN_CUSTOM_MINUTES,
            "allow_soft_blocked_apps": False,
            "last_selected_approver_uid": 0,
            "kiosk_muted": True,
            "child_muted": True,
        },
    }


def validate_preferences(raw: object) -> dict:
    # Personal-only accounts share the same schema/store without claiming that
    # the product ever installed policy for them. Readers see policy defaults.
    if isinstance(raw, dict) and set(raw) == {"version", "personal"}:
        raw = {**default_preferences(), **raw}
    if not isinstance(raw, dict) or set(raw) not in ({
        "version", "personal", "parent_control_enabled", "apps", "request",
    }, {
        "version", "parent_control_enabled", "daily_time_limit_minutes",
        "apps", "request", "personal",
    }):
        raise PreferencesError("preference record has invalid keys")
    if raw["version"] != FORMAT_VERSION or type(raw["version"]) is not int:
        raise PreferencesError("unsupported preference version")
    personal = raw["personal"]
    if (not isinstance(personal, dict) or "language" not in personal or
            not set(personal) <= {"language", "notifications"}):
        raise PreferencesError("invalid personal preferences")
    language = validate_language(personal["language"])
    notifications = validate_notifications(personal.get("notifications", default_notifications()))
    if type(raw["parent_control_enabled"]) is not bool:
        raise PreferencesError("parent-control state must be boolean")
    # Legacy v3 records could omit this field. Keep its grant-only default
    # when those records are migrated into the current schema.
    daily_limit = raw.get("daily_time_limit_minutes", MIN_DAILY_LIMIT_MINUTES)
    if (type(daily_limit) is not int or not
            MIN_DAILY_LIMIT_MINUTES <= daily_limit <= MAX_DAILY_LIMIT_MINUTES):
        raise PreferencesError("daily time limit must be an integer from 0 to 1440 minutes")
    if not isinstance(raw["apps"], dict):
        raise PreferencesError("apps must be an object")

    apps = {}
    for desktop_id, entry in raw["apps"].items():
        if not isinstance(desktop_id, str) or not DESKTOP_ID_RE.fullmatch(desktop_id):
            raise PreferencesError("invalid desktop application ID")
        if not isinstance(entry, dict) or set(entry) != {
            "state", "targets", "patterns", "user_saved_match_rule",
        }:
            raise PreferencesError("invalid application preference")
        state = entry["state"]
        if state not in VALID_APP_STATES:
            raise PreferencesError("invalid application state")
        if not isinstance(entry["targets"], list):
            raise PreferencesError("application targets must be an array")
        targets = tuple(validate_target(value) for value in entry["targets"])
        if len(targets) != len(set(targets)):
            raise PreferencesError("duplicate application target")
        if not isinstance(entry["patterns"], list):
            raise PreferencesError("application patterns must be an array")
        patterns = tuple(_validate_pattern(value, targets) for value in entry["patterns"])
        if len(patterns) != len(set(patterns)):
            raise PreferencesError("duplicate application pattern")
        user_saved_match_rule = entry["user_saved_match_rule"]
        if type(user_saved_match_rule) is not bool:
            raise PreferencesError("application match-rule override must be boolean")
        # Keep an allowed entry only when it carries a saved match-rule choice.
        # That choice must survive changing access back to allowed.
        if state != "allowed" or user_saved_match_rule:
            apps[desktop_id] = {
                "state": state, "targets": list(targets), "patterns": list(patterns),
                "user_saved_match_rule": user_saved_match_rule,
            }

    request = raw["request"]
    if (not isinstance(request, dict) or not REQUIRED_REQUEST_KEYS <= set(request) or
            not set(request) <= REQUIRED_REQUEST_KEYS | OPTIONAL_REQUEST_KEYS):
        raise PreferencesError("invalid request preferences")
    selected = request["last_selected_duration"]
    if selected not in VALID_DURATIONS:
        raise PreferencesError("invalid selected duration")
    custom = request["last_custom_minutes"]
    if (type(custom) not in (int, float) or not math.isfinite(custom) or
            not MIN_CUSTOM_MINUTES <= custom <= MAX_CUSTOM_MINUTES):
        raise PreferencesError("invalid custom duration")
    if type(request["allow_soft_blocked_apps"]) is not bool:
        raise PreferencesError("allow-soft state must be boolean")
    # Migrated legacy records can omit these optional request-form fields.
    # Preserve their defaults: first approver, and both request surfaces muted.
    approver_uid = request.get("last_selected_approver_uid", 0)
    if type(approver_uid) is not int or not 0 <= approver_uid <= UINT32_MAX:
        raise PreferencesError("invalid selected approver")
    kiosk_muted = request.get("kiosk_muted", True)
    child_muted = request.get("child_muted", True)
    if type(kiosk_muted) is not bool or type(child_muted) is not bool:
        raise PreferencesError("sound muted state must be boolean")

    return {
        "version": FORMAT_VERSION,
        "parent_control_enabled": raw["parent_control_enabled"],
        "personal": {"language": language, "notifications": notifications},
        "daily_time_limit_minutes": daily_limit,
        "apps": apps,
        "request": {
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": request["allow_soft_blocked_apps"],
            "last_selected_approver_uid": approver_uid,
            "kiosk_muted": kiosk_muted,
            "child_muted": child_muted,
        },
    }


def _validate_pattern(value: object, targets: tuple[str, ...]) -> str:
    """Validate the deliberately small, same-directory filename-glob contract."""
    if not isinstance(value, str) or not value.startswith("/"):
        raise PreferencesError("application pattern must be an absolute path")
    directory, separator, basename = value.rpartition("/")
    directory = directory or "/"
    if not separator or not basename or not any(char in basename for char in "*?"):
        raise PreferencesError("application pattern must contain a basename wildcard")
    if "/" in basename or any(char in basename for char in _UNSAFE_PATTERN_CHARACTERS):
        raise PreferencesError("application pattern contains unsupported characters")
    if any(char.isspace() for char in directory) or any(
            char in directory for char in _UNSAFE_PATTERN_CHARACTERS):
        raise PreferencesError("application pattern directory cannot be represented safely")
    resolved_directory = os.path.realpath(directory)
    if not any(target.startswith("/") and os.path.dirname(os.path.realpath(target)) == resolved_directory
               for target in targets):
        raise PreferencesError("application pattern must share a directory with its target")
    return f"{resolved_directory.rstrip('/')}/{basename}" if resolved_directory != "/" else f"/{basename}"


def blocked_targets(preferences: dict, allow_soft: bool) -> tuple[str, ...]:
    targets = []
    for entry in preferences["apps"].values():
        if entry["state"] == "permanent" or (
                entry["state"] == "conditional" and not allow_soft):
            targets.extend(entry["targets"])
    return tuple(sorted(set(targets)))


def blocked_patterns(preferences: dict, allow_soft: bool) -> tuple[str, ...]:
    """Return active native filename patterns using the same soft-block state."""
    patterns = []
    for entry in preferences["apps"].values():
        if entry["state"] == "permanent" or (
                entry["state"] == "conditional" and not allow_soft):
            patterns.extend(entry["patterns"])
    return tuple(sorted(set(patterns)))


def _unique_preference_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PreferencesError("duplicate preference key")
        value[key] = item
    return value


def decode_preferences(text: str) -> object:
    """Decode one record without silently accepting duplicate settings."""
    return json.loads(text, object_pairs_hook=_unique_preference_keys)


@dataclass
class PreferenceStore:
    directory: Path = Path("/var/lib/oh-no-parent-control/preferences")
    _write_lock: threading.RLock = field(default_factory=threading.RLock,
                                        init=False, repr=False, compare=False)

    def _path(self, uid: int) -> Path:
        if type(uid) is not int or not 0 <= uid <= UINT32_MAX:
            raise PreferencesError("invalid preference UID")
        return self.directory / f"{uid}.json"

    def load(self, uid: int) -> dict:
        raw = self._load_record(uid)
        try:
            return validate_preferences(raw)
        except PreferencesError as error:
            LOG.warning("preferences.003", error_type=error_code(error))
            raise

    def _load_record(self, uid: int) -> object:
        path = self._path(uid)
        try:
            raw = decode_preferences(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            LOG.info("preferences.001")
            return {"version": FORMAT_VERSION, "personal": {"language": ""}}
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            LOG.warning("preferences.002", error_type=error_code(error))
            raise PreferencesError("could not read preferences") from error
        return raw

    def save(self, uid: int, preferences: object) -> dict:
        normalized = validate_preferences(preferences)
        with self._write_lock:
            # Policy/request writes, including rollback, never overwrite a
            # newer personal selection from a stale frontend snapshot.
            normalized["personal"] = self.load(uid)["personal"]
            return self._write(uid, normalized)

    def update_language(self, uid: int, language: object) -> str:
        language = validate_language(language)
        with self._write_lock:
            raw = self._load_record(uid)
            current = validate_preferences(raw)
            current["personal"] = {**current["personal"], "language": language}
            if set(raw) == {"version", "personal"}:
                current = {"version": FORMAT_VERSION, "personal": current["personal"]}
            return self._write(uid, current)["personal"]["language"]

    def update_notifications(self, uid: int, notifications: object) -> dict:
        notifications = validate_notifications(notifications)
        with self._write_lock:
            raw = self._load_record(uid)
            current = validate_preferences(raw)
            current["personal"]["notifications"] = notifications
            if set(raw) == {"version", "personal"}:
                current = {"version": FORMAT_VERSION, "personal": current["personal"]}
            return self._write(uid, current)["personal"]["notifications"]

    def _write(self, uid: int, normalized: dict) -> dict:
        LOG.info("preferences.004", app_policy_count=len(normalized.get("apps", {})))
        path = self._path(uid)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{uid}.", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(normalized, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            LOG.error("preferences.005", error_type=error_code(error))
            raise
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        LOG.info("preferences.006")
        return normalized

    def update_request(self, uid: int, selected: str, custom: float,
                       allow_soft: bool, last_selected_approver_uid: int = 0) -> dict:
        current = self.load(uid)
        current["request"] = {
            **current["request"],
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": allow_soft,
            "last_selected_approver_uid": last_selected_approver_uid,
        }
        return self.save(uid, current)

    def update_request_muted(self, uid: int, surface: str, muted: bool) -> dict:
        if surface not in {"kiosk", "child"}:
            raise PreferencesError("invalid request sound surface")
        if type(muted) is not bool:
            raise PreferencesError("sound muted state must be boolean")
        current = self.load(uid)
        key = "kiosk_muted" if surface == "kiosk" else "child_muted"
        current["request"] = {**current["request"], key: muted}
        return self.save(uid, current)
