"""Strict, fail-closed broker configuration loading."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

UINT32_MAX = (1 << 32) - 1
MAX_REQUEST_INTERVAL = 3600
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FLATPAK_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$"
)
TOP_KEYS = {
    "version", "kiosk_uid", "child_uid", "child_label", "durations",
    "app_filter_profiles", "minimum_request_interval_seconds",
}
DURATION_KEYS = {"label", "seconds"}
PROFILE_KEYS = {"label", "blocked_targets"}


class ConfigurationError(ValueError):
    """Configuration is invalid or not safely owned."""


@dataclass(frozen=True)
class Duration:
    label: str
    seconds: int | str


@dataclass(frozen=True)
class FilterProfile:
    label: str
    blocked_targets: tuple[str, ...]


@dataclass(frozen=True)
class Configuration:
    kiosk_uid: int
    child_uid: int
    child_label: str
    durations: Mapping[str, Duration]
    app_filter_profiles: Mapping[str, FilterProfile]
    minimum_request_interval_seconds: int


def _object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"duplicate key: {key}")
        result[key] = value
    return result


def _exact_keys(value, expected, where):
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        raise ConfigurationError(f"unknown {where} key: {sorted(unknown)[0]}")
    if missing:
        raise ConfigurationError(f"missing {where} key: {sorted(missing)[0]}")


def _label(value, where):
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise ConfigurationError(f"{where} must be a non-empty label")
    return value.strip()


def _choice_id(value, where):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ConfigurationError(f"invalid {where} ID")
    return value


def validate_target(target: object) -> str:
    if not isinstance(target, str) or not target or "\x00" in target:
        raise ConfigurationError("app-filter targets must be non-empty strings")
    if target.startswith("/"):
        if target != os.path.normpath(target) or target == "/":
            raise ConfigurationError(f"invalid executable path: {target}")
        return target
    if not FLATPAK_ID_RE.fullmatch(target):
        raise ConfigurationError(f"invalid Flatpak application ID: {target}")
    return target


def validate(raw: object, *, uid_min: int = 1000) -> Configuration:
    _exact_keys(raw, TOP_KEYS, "top-level")
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise ConfigurationError("version must be 1")
    kiosk_uid = raw["kiosk_uid"]
    child_uid = raw["child_uid"]
    if type(kiosk_uid) is not int or kiosk_uid <= 0 or kiosk_uid > UINT32_MAX:
        raise ConfigurationError("kiosk_uid must be a nonzero numeric UID")
    if type(child_uid) is not int or child_uid < uid_min or child_uid > UINT32_MAX:
        raise ConfigurationError("child_uid must identify a non-system user")
    if kiosk_uid == child_uid:
        raise ConfigurationError("kiosk_uid and child_uid must differ")

    durations_raw = raw["durations"]
    if not isinstance(durations_raw, dict) or not durations_raw:
        raise ConfigurationError("durations must be a non-empty object")
    durations = {}
    labels = set()
    logical_durations = set()
    for duration_id, item in durations_raw.items():
        _choice_id(duration_id, "duration")
        _exact_keys(item, DURATION_KEYS, f"duration {duration_id}")
        label = _label(item["label"], f"duration {duration_id} label")
        folded = label.casefold()
        if folded in labels:
            raise ConfigurationError("duplicate duration label")
        labels.add(folded)
        seconds = item["seconds"]
        if seconds != "local-midnight" and (
            type(seconds) is not int or seconds <= 0 or seconds > UINT32_MAX
        ):
            raise ConfigurationError(f"invalid duration seconds: {duration_id}")
        if seconds in logical_durations:
            raise ConfigurationError("duplicate logical duration")
        logical_durations.add(seconds)
        durations[duration_id] = Duration(label, seconds)

    profiles_raw = raw["app_filter_profiles"]
    if not isinstance(profiles_raw, dict):
        raise ConfigurationError("app_filter_profiles must be an object")
    profiles = {}
    labels = set()
    logical_profiles = set()
    for profile_id, item in profiles_raw.items():
        _choice_id(profile_id, "profile")
        _exact_keys(item, PROFILE_KEYS, f"profile {profile_id}")
        label = _label(item["label"], f"profile {profile_id} label")
        folded = label.casefold()
        if folded in labels:
            raise ConfigurationError("duplicate profile label")
        labels.add(folded)
        targets_raw = item["blocked_targets"]
        if not isinstance(targets_raw, list):
            raise ConfigurationError("blocked_targets must be an array")
        targets = tuple(validate_target(value) for value in targets_raw)
        if len(targets) != len(set(targets)):
            raise ConfigurationError("duplicate blocked target")
        canonical_targets = tuple(sorted(targets))
        if canonical_targets in logical_profiles:
            raise ConfigurationError("duplicate logical filter profile")
        logical_profiles.add(canonical_targets)
        profiles[profile_id] = FilterProfile(label, targets)

    interval = raw["minimum_request_interval_seconds"]
    if type(interval) is not int or not 1 <= interval <= MAX_REQUEST_INTERVAL:
        raise ConfigurationError("minimum request interval is out of range")
    return Configuration(
        kiosk_uid=kiosk_uid,
        child_uid=child_uid,
        child_label=_label(raw["child_label"], "child_label"),
        durations=durations,
        app_filter_profiles=profiles,
        minimum_request_interval_seconds=interval,
    )


def load(path: str | os.PathLike, *, require_secure_file: bool = True) -> Configuration:
    path = Path(path)
    stream = None
    try:
        if require_secure_file:
            parent_stat = path.parent.stat()
            if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != 0:
                raise ConfigurationError("configuration directory must be owned by root")
            if parent_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ConfigurationError("configuration directory is writable by group or other")
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            file_stat = os.fstat(descriptor)
            stream = os.fdopen(descriptor, "r", encoding="utf-8")
        else:
            stream = path.open("r", encoding="utf-8")
            file_stat = os.fstat(stream.fileno())
    except ConfigurationError:
        raise
    except OSError as error:
        raise ConfigurationError(f"cannot open configuration: {error.strerror}") from error
    if require_secure_file:
        if not stat.S_ISREG(file_stat.st_mode):
            stream.close()
            raise ConfigurationError("configuration is not a regular file")
        if file_stat.st_uid != 0:
            stream.close()
            raise ConfigurationError("configuration must be owned by root")
        if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            stream.close()
            raise ConfigurationError("configuration is writable by group or other")
    try:
        with stream:
            raw = json.load(stream, object_pairs_hook=_object_no_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"cannot parse configuration: {error}") from error
    return validate(raw)
