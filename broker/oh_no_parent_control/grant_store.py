"""Broker-private, per-child saved time and grant-transfer records.

Each managed child has at most one record, ``grants/<uid>.json``. It is bound
to the account's UID and username and carries a revision that changes on every
write, including clears. Callers serialize writers under the broker transaction
lock; the store keeps each replacement atomic and refuses stale revisions.
Errors are typed and never name the account, so callers can log them safely.
"""

from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import UINT32_MAX
from .data_migration import (
    GRANTS_DIRECTORY, MigrationError, _atomic_write, _fsync_directory, _read_record,
)
from .preferences import MAX_TIME_GRANT_SECONDS

FORMAT_VERSION = 1
UINT64_MAX = 2 ** 64 - 1
MAX_USERNAME_LENGTH = 256
MAX_SAVED_SECONDS = MAX_TIME_GRANT_SECONDS
"""A saved balance never exceeds the existing maximum single grant."""

GrantTuple = tuple[int, int]
"""An ``ActiveExtension`` value: issuance epoch seconds and duration seconds."""


class GrantStoreError(RuntimeError):
    """The record is unsupported, corrupt, unsafe, stale or cannot be stored."""


class GrantAccountError(GrantStoreError):
    """The record no longer belongs to the live account with this UID."""


@dataclass(frozen=True)
class FixedGrant:
    """The last tuple the broker wrote as fixed, and whether a pause ended it."""
    grant: GrantTuple
    allow_soft_blocked_apps: bool
    ended_by_pause: bool = False


@dataclass(frozen=True)
class SavedBalance:
    seconds: int
    allow_soft_blocked_apps: bool


@dataclass(frozen=True)
class PauseIntent:
    """Shorten ``source`` to ``destination`` and then commit ``saved``."""
    source: GrantTuple
    destination: GrantTuple
    saved: SavedBalance


@dataclass(frozen=True)
class RedeemIntent:
    """Replace ``source`` with ``destination`` using the saved app choice."""
    source: GrantTuple
    destination: GrantTuple
    allow_soft_blocked_apps: bool
    record_fixed: bool


@dataclass(frozen=True)
class GrantRecord:
    """Revision 0 means that no record has been written for this UID."""
    uid: int
    username: str
    revision: int = 0
    fixed: FixedGrant | None = None
    saved: SavedBalance | None = None
    intent: PauseIntent | RedeemIntent | None = None

    def document(self) -> dict:
        return {
            "version": FORMAT_VERSION, "uid": self.uid, "username": self.username,
            "revision": self.revision,
            "fixed": None if self.fixed is None else {
                **_tuple_document(self.fixed.grant),
                "allow_soft_blocked_apps": self.fixed.allow_soft_blocked_apps,
                "ended_by_pause": self.fixed.ended_by_pause,
            },
            "saved": _saved_document(self.saved),
            "intent": _intent_document(self.intent),
        }


def _tuple_document(value: GrantTuple) -> dict:
    return {"issued_at": value[0], "duration": value[1]}


def _saved_document(saved: SavedBalance | None) -> dict | None:
    return None if saved is None else {
        "seconds": saved.seconds, "allow_soft_blocked_apps": saved.allow_soft_blocked_apps}


def _intent_document(intent: PauseIntent | RedeemIntent | None) -> dict | None:
    if intent is None:
        return None
    common = {"source": _tuple_document(intent.source),
              "destination": _tuple_document(intent.destination)}
    if isinstance(intent, PauseIntent):
        return {"kind": "pause", **common, "saved": _saved_document(intent.saved)}
    return {"kind": "redeem", **common,
            "allow_soft_blocked_apps": intent.allow_soft_blocked_apps,
            "record_fixed": intent.record_fixed}


def _object(raw: object, keys: set[str], name: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != keys:
        raise GrantStoreError(f"grant record has invalid {name} keys")
    return raw


def _integer(value: object, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise GrantStoreError(f"grant record has an invalid {name}")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise GrantStoreError(f"grant record has an invalid {name}")
    return value


def _parse_tuple(raw: object, name: str, *, running: bool) -> GrantTuple:
    raw = _object(raw, {"issued_at", "duration"}, name)
    return (_integer(raw["issued_at"], 0, UINT64_MAX, f"{name} issuance"),
            _integer(raw["duration"], int(running), UINT32_MAX, f"{name} duration"))


def _parse_saved(raw: object) -> SavedBalance:
    raw = _object(raw, {"seconds", "allow_soft_blocked_apps"}, "saved balance")
    return SavedBalance(_integer(raw["seconds"], 1, MAX_SAVED_SECONDS, "saved balance"),
                        _boolean(raw["allow_soft_blocked_apps"], "saved app choice"))


def _parse_intent(raw: object) -> PauseIntent | RedeemIntent:
    kind = raw.get("kind") if isinstance(raw, dict) else None
    if kind == "pause":
        raw = _object(raw, {"kind", "source", "destination", "saved"}, "pause intent")
        source = _parse_tuple(raw["source"], "pause source", running=True)
        destination = _parse_tuple(raw["destination"], "pause destination", running=True)
        # The pause step only ever shortens the same issued tuple.
        if destination[0] != source[0] or destination[1] >= source[1]:
            raise GrantStoreError("grant record has an invalid pause destination")
        return PauseIntent(source, destination, _parse_saved(raw["saved"]))
    if kind == "redeem":
        raw = _object(raw, {"kind", "source", "destination", "allow_soft_blocked_apps",
                            "record_fixed"}, "redemption intent")
        return RedeemIntent(
            _parse_tuple(raw["source"], "redemption source", running=False),
            _parse_tuple(raw["destination"], "redemption destination", running=True),
            _boolean(raw["allow_soft_blocked_apps"], "redemption app choice"),
            _boolean(raw["record_fixed"], "redemption fixed marker"))
    raise GrantStoreError("grant record has an invalid intent kind")


def parse_grant_record(raw: object) -> GrantRecord:
    """Validate one decoded current-schema record without account lookups."""
    raw = _object(raw, {"version", "uid", "username", "revision", "fixed", "saved", "intent"},
                  "top-level")
    if type(raw["version"]) is not int or raw["version"] != FORMAT_VERSION:
        raise GrantStoreError("grant record has an unsupported schema version")
    username = raw["username"]
    if (not isinstance(username, str) or not 0 < len(username) <= MAX_USERNAME_LENGTH or
            "\x00" in username or "/" in username):
        raise GrantStoreError("grant record has an invalid username")
    fixed = None
    if raw["fixed"] is not None:
        entry = _object(raw["fixed"], {"issued_at", "duration", "allow_soft_blocked_apps",
                                       "ended_by_pause"}, "fixed grant")
        fixed = FixedGrant(
            _parse_tuple({"issued_at": entry["issued_at"], "duration": entry["duration"]},
                         "fixed grant", running=True),
            _boolean(entry["allow_soft_blocked_apps"], "fixed app choice"),
            _boolean(entry["ended_by_pause"], "fixed pause marker"))
    intent = None if raw["intent"] is None else _parse_intent(raw["intent"])
    # A pause starts only from the recorded, still-running fixed tuple.
    if isinstance(intent, PauseIntent) and (
            fixed is None or fixed.grant != intent.source or fixed.ended_by_pause):
        raise GrantStoreError("grant record has a pause intent without its fixed grant")
    return GrantRecord(
        uid=_integer(raw["uid"], 0, UINT32_MAX, "UID"),
        username=username,
        revision=_integer(raw["revision"], 1, UINT64_MAX, "revision"),
        fixed=fixed,
        saved=None if raw["saved"] is None else _parse_saved(raw["saved"]),
        intent=intent,
    )


def validate_grant_record(raw: object) -> dict:
    """Current-schema validator for the pure JSON migration pass."""
    return parse_grant_record(raw).document()


# Balance arithmetic in integer seconds at one evaluation time ``now``:
# D daily time remaining, A running-grant remaining, S saved, X = max(0, A - D).

def _seconds(value: object, maximum: int = UINT32_MAX) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("time value is outside the supported range")
    return value


def remaining_seconds(grant: GrantTuple, now: int) -> int:
    """A: the seconds a live ``ActiveExtension`` tuple still runs at ``now``."""
    issued, duration = grant
    remaining = max(0, _seconds(issued, UINT64_MAX) + _seconds(duration) -
                    _seconds(now, UINT64_MAX))
    return _seconds(remaining)


def beyond_daily_seconds(daily: int, running: int) -> int:
    """X: running approved time beyond today's daily time."""
    return max(0, _seconds(running) - _seconds(daily))


def merged_saved_seconds(saved: int, added: int) -> int:
    """S + X or S + N, refusing a balance beyond the saved-time limit."""
    return _seconds(_seconds(saved) + _seconds(added), MAX_SAVED_SECONDS)


def running_mode(record: GrantRecord, live: GrantTuple, remaining: int) -> str:
    """Derive ``none``, ``fixed`` or ``deadline``; the mode is never stored.

    Only the recorded fixed tuple is fixed. Its pause-ended form counts as
    ended. Pre-feature, rest-of-day and external tuples are deadline grants.
    """
    fixed = record.fixed if record.fixed is not None and record.fixed.grant == live else None
    if _seconds(remaining) == 0 or (fixed is not None and fixed.ended_by_pause):
        return "none"
    return "deadline" if fixed is None else "fixed"


def new_grant_is_fixed(record: GrantRecord, live: GrantTuple, daily: int, remaining: int) -> bool:
    """Whether a grant replacing ``live`` with ``max(D, A) + seconds`` is fixed.

    It stays a deadline grant when it absorbed a running deadline grant that
    still contributed time beyond daily time.
    """
    return not (beyond_daily_seconds(daily, remaining) > 0 and
                running_mode(record, live, remaining) == "deadline")


@dataclass
class GrantStore:
    directory: Path = GRANTS_DIRECTORY
    _lock: threading.Lock = field(default_factory=threading.Lock,
                                  init=False, repr=False, compare=False)

    def load(self, uid: int, username: str) -> GrantRecord:
        """Read the record of the live eligible account ``uid``/``username``.

        Absent records read as revision 0 with nothing saved. A record bound to
        another account raises ``GrantAccountError``; callers clear it.
        """
        with self._lock:
            record = self._read(uid)
        if record is None:
            return GrantRecord(uid, username)
        if record.username != username:
            raise GrantAccountError("grant record belongs to a different account")
        return record

    def write(self, record: GrantRecord) -> GrantRecord:
        """Replace the record read at ``record.revision`` with ``record``.

        A ``GrantStoreError`` after the replacement step can still leave the
        new record published; callers reread instead of assuming no change.
        """
        with self._lock:
            current = self._read(record.uid)
            if (0 if current is None else current.revision) != record.revision:
                raise GrantStoreError("grant record changed since it was read")
            if current is not None and current.username != record.username:
                raise GrantAccountError("grant record belongs to a different account")
            return self._replace(record, current)

    def clear(self, uid: int, username: str) -> GrantRecord:
        """Invalidate saved time, fixed tracking and intent for this account.

        A clear writes an empty record with a new revision, including over a
        record bound to another account, so old revisions never repeat.
        """
        with self._lock:
            current = self._read(uid)
            return self._replace(GrantRecord(uid, username), current)

    def _path(self, uid: int) -> Path:
        if type(uid) is not int or not 0 <= uid <= UINT32_MAX:
            raise GrantStoreError("invalid grant record UID")
        return self.directory / f"{uid}.json"

    def _directory_exists(self, *, create: bool) -> bool:
        try:
            try:
                info = self.directory.lstat()
            except FileNotFoundError:
                if not create:
                    return False
                # The broker's StateDirectory owns the parent; never create it.
                self.directory.mkdir(mode=0o700)
                os.chmod(self.directory, 0o700)
                _fsync_directory(self.directory.parent)
                info = self.directory.lstat()
        except OSError as error:
            raise GrantStoreError("grant directory is unavailable") from error
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or
                stat.S_IMODE(info.st_mode) & 0o077):
            raise GrantStoreError("grant directory has unsafe type, ownership or permissions")
        return True

    def _read(self, uid: int) -> GrantRecord | None:
        path = self._path(uid)
        if not self._directory_exists(create=False):
            return None
        try:
            path.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise GrantStoreError("grant record cannot be inspected") from error
        try:
            raw, _file_stat = _read_record(path)
        except MigrationError as error:
            raise GrantStoreError("grant record is unreadable or unsafe") from error
        record = parse_grant_record(raw)
        if record.uid != uid:
            raise GrantStoreError("grant record UID does not match its name")
        return record

    def _replace(self, record: GrantRecord, current: GrantRecord | None) -> GrantRecord:
        revision = 1 if current is None else current.revision + 1
        if revision > UINT64_MAX:
            raise GrantStoreError("grant record revision is exhausted")
        # Validate the complete result before anything reaches the disk.
        written = parse_grant_record(replace(record, revision=revision).document())
        path = self._path(record.uid)
        self._directory_exists(create=True)
        try:
            _atomic_write(path, written.document(), self.directory.lstat())
        except (MigrationError, OSError) as error:
            raise GrantStoreError("grant record could not be stored") from error
        return written
