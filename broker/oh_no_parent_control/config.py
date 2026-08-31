"""Strict, fail-closed broker configuration loading."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path


UINT32_MAX = (1 << 32) - 1
MAX_REQUEST_INTERVAL = 3600
FLATPAK_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)+$"
)
FLATPAK_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TOP_KEYS = {
    "version", "kiosk_uid", "minimum_request_interval_seconds",
}


class ConfigurationError(ValueError):
    """Configuration is invalid or not safely owned."""


@dataclass(frozen=True)
class Configuration:
    kiosk_uid: int
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


def validate_target(target: object) -> str:
    if not isinstance(target, str) or not target or "\x00" in target:
        raise ConfigurationError("app-filter targets must be non-empty strings")
    if target.startswith("/"):
        if target != os.path.normpath(target) or target == "/":
            raise ConfigurationError(f"invalid executable path: {target}")
        return target
    parts = target.split("/")
    if (len(parts) == 4 and parts[0] == "app" and
            FLATPAK_ID_RE.fullmatch(parts[1]) and
            all(FLATPAK_COMPONENT_RE.fullmatch(part) for part in parts[2:])):
        return target
    if not FLATPAK_ID_RE.fullmatch(target):
        raise ConfigurationError(f"invalid Flatpak application target: {target}")
    return target


def validate(raw: object) -> Configuration:
    _exact_keys(raw, TOP_KEYS, "top-level")
    if type(raw["version"]) is not int or raw["version"] != 3:
        raise ConfigurationError("version must be 3")
    kiosk_uid = raw["kiosk_uid"]
    if type(kiosk_uid) is not int or kiosk_uid <= 0 or kiosk_uid > UINT32_MAX:
        raise ConfigurationError("kiosk_uid must be a nonzero numeric UID")

    interval = raw["minimum_request_interval_seconds"]
    if type(interval) is not int or not 1 <= interval <= MAX_REQUEST_INTERVAL:
        raise ConfigurationError("minimum request interval is out of range")
    return Configuration(
        kiosk_uid=kiosk_uid,
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
