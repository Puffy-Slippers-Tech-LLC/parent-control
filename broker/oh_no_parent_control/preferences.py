"""Root-owned, per-child preferences with strict validation and atomic writes."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import UINT32_MAX, validate_target

FORMAT_VERSION = 2
VALID_APP_STATES = {"allowed", "permanent", "conditional"}
MIN_DAILY_LIMIT_MINUTES = 0
MAX_DAILY_LIMIT_MINUTES = 24 * 60
MIN_CUSTOM_MINUTES = 0.1
MAX_CUSTOM_MINUTES = 1440
VALID_DURATIONS = {"custom", "0", "300", "900", "1800", "3600", "7200", "14400"}
DESKTOP_ID_RE = re.compile(r"^[^/\x00]+\.desktop$")
_UNSAFE_PATTERN_CHARACTERS = frozenset(",\"\\\x00\r\n")


class PreferencesError(ValueError):
    """A preference record is malformed or could not be stored safely."""


def default_preferences() -> dict:
    return {
        "version": FORMAT_VERSION,
        "parent_control_enabled": False,
        "daily_time_limit_minutes": MIN_DAILY_LIMIT_MINUTES,
        "apps": {},
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": MIN_CUSTOM_MINUTES,
            "allow_soft_blocked_apps": False,
        },
    }


def validate_preferences(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) not in ({
        "version", "parent_control_enabled", "apps", "request",
    }, {
        "version", "parent_control_enabled", "daily_time_limit_minutes",
        "apps", "request",
    }):
        raise PreferencesError("preference record has invalid keys")
    if raw["version"] != FORMAT_VERSION or type(raw["version"]) is not int:
        raise PreferencesError("unsupported preference version")
    if type(raw["parent_control_enabled"]) is not bool:
        raise PreferencesError("parent-control state must be boolean")
    # This field was added without changing FORMAT_VERSION. Records carrying
    # that same current version must therefore normalize its omission to the
    # grant-only default instead of becoming unreadable.
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
        if not isinstance(entry, dict) or set(entry) != {"state", "targets", "patterns"}:
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
        if state != "allowed":
            apps[desktop_id] = {
                "state": state, "targets": list(targets), "patterns": list(patterns),
            }

    request = raw["request"]
    if not isinstance(request, dict) or set(request) != {
        "last_selected_duration", "last_custom_minutes", "allow_soft_blocked_apps",
    }:
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

    return {
        "version": FORMAT_VERSION,
        "parent_control_enabled": raw["parent_control_enabled"],
        "daily_time_limit_minutes": daily_limit,
        "apps": apps,
        "request": {
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": request["allow_soft_blocked_apps"],
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


@dataclass
class PreferenceStore:
    directory: Path = Path("/var/lib/oh-no-parent-control/preferences")

    def _path(self, uid: int) -> Path:
        if type(uid) is not int or not 0 < uid <= UINT32_MAX:
            raise PreferencesError("invalid preference UID")
        return self.directory / f"{uid}.json"

    def load(self, uid: int) -> dict:
        path = self._path(uid)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default_preferences()
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PreferencesError("could not read preferences") from error
        return validate_preferences(raw)

    def save(self, uid: int, preferences: object) -> dict:
        normalized = validate_preferences(preferences)
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
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return normalized

    def update_request(self, uid: int, selected: str, custom: float,
                       allow_soft: bool) -> dict:
        current = self.load(uid)
        current["request"] = {
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": allow_soft,
        }
        return self.save(uid, current)
