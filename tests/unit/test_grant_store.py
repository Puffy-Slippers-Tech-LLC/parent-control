import json
import os
import stat
from dataclasses import replace
from unittest import mock

import pytest

from oh_no_parent_control.data_migration import MigrationError, migrate_all_state
from oh_no_parent_control.grant_store import (
    FixedGrant, GrantAccountError, GrantRecord, GrantStore, GrantStoreError, MAX_SAVED_SECONDS,
    PauseIntent, RedeemIntent, SavedBalance, UINT64_MAX, beyond_daily_seconds,
    merged_saved_seconds, new_grant_is_fixed, remaining_seconds, running_mode,
)
from oh_no_parent_control.config import UINT32_MAX
from oh_no_parent_control.core import InvalidRequest, calculate_active_extension_seconds
from oh_no_parent_control.preferences import MAX_TIME_GRANT_SECONDS


UID = 1001
USERNAME = "riley-account"


@pytest.fixture
def directory(tmp_path):
    tmp_path.chmod(0o700)
    return tmp_path / "grants"


def paused_record(store):
    record = store.load(UID, USERNAME)
    return replace(
        record,
        fixed=FixedGrant((1_700_000_000, 1200), True),
        saved=SavedBalance(600, False),
        intent=PauseIntent((1_700_000_000, 1200), (1_700_000_000, 900), SavedBalance(900, False)),
    )


def write_raw(directory, document, uid=UID, mode=0o600):
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / f"{uid}.json"
    path.write_text(document if isinstance(document, str) else json.dumps(document),
                    encoding="utf-8")
    path.chmod(mode)
    return path


def test_absent_record_reads_as_revision_zero_without_creating_storage(directory):
    record = GrantStore(directory).load(UID, USERNAME)

    assert record == GrantRecord(UID, USERNAME)
    assert (record.revision, record.saved, record.fixed, record.intent) == (0, None, None, None)
    assert not directory.exists()


def test_records_round_trip_atomically_with_private_modes_and_new_revisions(directory):
    store = GrantStore(directory)
    written = store.write(paused_record(store))

    assert written.revision == 1
    assert GrantStore(directory).load(UID, USERNAME) == written
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / f"{UID}.json").stat().st_mode) == 0o600
    assert [path.name for path in directory.iterdir()] == [f"{UID}.json"]

    redeem = RedeemIntent((1_700_000_000, 900), (1_700_000_100, 4200), False, True)
    committed = store.write(replace(written, intent=redeem))
    assert committed.revision == 2
    assert store.load(UID, USERNAME).intent == redeem

    # A clear is a valid empty record, distinct from an absent one.
    cleared = store.clear(UID, USERNAME)
    assert cleared == GrantRecord(UID, USERNAME, revision=3)
    assert store.load(UID, USERNAME) == cleared
    assert store.clear(UID, USERNAME).revision == 4


def test_stale_revision_is_refused_without_changing_the_record(directory):
    store = GrantStore(directory)
    first = store.write(paused_record(store))
    path = directory / f"{UID}.json"
    before = path.read_bytes()

    with pytest.raises(GrantStoreError, match="changed since"):
        store.write(replace(first, revision=0, saved=SavedBalance(1, True)))
    assert path.read_bytes() == before

    # A clear cannot be undone by a writer holding the revision before it.
    store.clear(UID, USERNAME)
    with pytest.raises(GrantStoreError, match="changed since"):
        store.write(replace(first, saved=SavedBalance(1, True)))
    assert store.load(UID, USERNAME) == GrantRecord(UID, USERNAME, revision=2)


def test_account_change_is_detected_at_read_and_cleared_with_a_new_revision(directory):
    store = GrantStore(directory)
    old = store.write(paused_record(store))

    with pytest.raises(GrantAccountError) as raised:
        store.load(UID, "replacement-account")
    with pytest.raises(GrantAccountError):
        store.write(replace(old, username="replacement-account"))
    assert USERNAME not in str(raised.value) and str(UID) not in str(raised.value)

    cleared = store.clear(UID, "replacement-account")
    assert cleared.revision == old.revision + 1
    assert store.load(UID, "replacement-account") == cleared
    with pytest.raises(GrantAccountError):
        store.load(UID, USERNAME)


def test_children_have_independent_records_and_revisions(directory):
    store = GrantStore(directory)
    store.write(paused_record(store))
    store.write(replace(store.load(UID, USERNAME), saved=SavedBalance(5, True)))
    other = store.write(replace(store.load(1002, "other-child"), saved=SavedBalance(60, False)))

    assert other.revision == 1
    assert store.load(UID, USERNAME).revision == 2
    store.clear(1002, "other-child")
    assert store.load(UID, USERNAME).saved == SavedBalance(5, True)


@pytest.mark.parametrize("make", ["symlink", "directory", "fifo"])
def test_symlinks_and_non_regular_records_are_refused(directory, tmp_path, make):
    directory.mkdir(mode=0o700)
    path = directory / f"{UID}.json"
    if make == "symlink":
        target = tmp_path / "elsewhere.json"
        target.write_text(json.dumps(GrantRecord(UID, USERNAME, 1).document()))
        target.chmod(0o600)
        path.symlink_to(target)
    elif make == "directory":
        path.mkdir()
    else:
        os.mkfifo(path, 0o600)

    store = GrantStore(directory)
    with pytest.raises(GrantStoreError):
        store.load(UID, USERNAME)
    with pytest.raises(GrantStoreError):
        store.clear(UID, USERNAME)
    assert path.is_symlink() or not path.is_file()


def test_unsafe_directory_and_record_modes_and_ownership_are_refused(directory, tmp_path):
    path = write_raw(directory, GrantRecord(UID, USERNAME, 1).document(), mode=0o640)
    with pytest.raises(GrantStoreError):
        GrantStore(directory).load(UID, USERNAME)

    path.chmod(0o600)
    directory.chmod(0o750)
    with pytest.raises(GrantStoreError, match="unsafe"):
        GrantStore(directory).load(UID, USERNAME)

    directory.chmod(0o700)
    with mock.patch("os.geteuid", return_value=os.geteuid() + 1):
        with pytest.raises(GrantStoreError, match="unsafe"):
            GrantStore(directory).load(UID, USERNAME)

    link = tmp_path / "linked-grants"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(GrantStoreError, match="unsafe"):
        GrantStore(link).write(GrantRecord(UID, USERNAME))


def valid_document():
    return GrantRecord(
        UID, USERNAME, 7, FixedGrant((10, 20), False, True), SavedBalance(30, True),
        RedeemIntent((0, 0), (40, 50), True, False)).document()


def mutate(path, value):
    def apply(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return document
    return apply


@pytest.mark.parametrize("change", [
    mutate(("version",), 2),
    mutate(("version",), 0),
    mutate(("version",), True),
    mutate(("revision",), 0),
    mutate(("revision",), UINT64_MAX + 1),
    mutate(("uid",), 1002),
    mutate(("username",), ""),
    mutate(("username",), "x" * 257),
    mutate(("saved", "seconds"), 0),
    mutate(("saved", "seconds"), UINT32_MAX + 1),
    mutate(("saved", "allow_soft_blocked_apps"), 1),
    mutate(("fixed", "issued_at"), UINT64_MAX + 1),
    mutate(("fixed", "duration"), 0),
    mutate(("fixed", "duration"), -1),
    mutate(("fixed", "duration"), 1.5),
    mutate(("intent", "kind"), "resume"),
    mutate(("intent", "destination", "duration"), 0),
    mutate(("intent", "record_fixed"), None),
    mutate(("intent", "extra"), 1),
    mutate(("future_field",), 1),
])
def test_malformed_future_and_out_of_bounds_records_are_refused_and_preserved(directory, change):
    path = write_raw(directory, change(valid_document()))
    before = path.read_bytes()
    store = GrantStore(directory)

    with pytest.raises(GrantStoreError) as raised:
        store.load(UID, USERNAME)
    # Unsupported data is never replaced: callers cannot learn its revision.
    with pytest.raises(GrantStoreError):
        store.clear(UID, USERNAME)
    assert path.read_bytes() == before
    assert USERNAME not in str(raised.value) and str(UID) not in str(raised.value)


def test_pause_intent_must_shorten_its_own_tuple(directory):
    document = valid_document()
    document["intent"] = {"kind": "pause", "source": {"issued_at": 10, "duration": 20},
                          "destination": {"issued_at": 11, "duration": 15},
                          "saved": {"seconds": 5, "allow_soft_blocked_apps": True}}
    write_raw(directory, document)
    with pytest.raises(GrantStoreError, match="pause destination"):
        GrantStore(directory).load(UID, USERNAME)


@pytest.mark.parametrize("fixed", [
    None,
    FixedGrant((1_700_000_000, 1300), True),
    FixedGrant((1_700_000_000, 1200), True, ended_by_pause=True),
])
def test_pause_intent_requires_the_running_recorded_fixed_grant(directory, fixed):
    store = GrantStore(directory)
    with pytest.raises(GrantStoreError, match="without its fixed grant"):
        store.write(replace(paused_record(store), fixed=fixed))
    assert not (directory / f"{UID}.json").exists()


@pytest.mark.parametrize("text", [
    '{"version": 1, "version": 1}',
    '{"version": 1',
    '[]',
    '\udcff',
    '{"version": ' + '1' * 5000 + '}',
])
def test_duplicate_keys_and_undecodable_records_are_refused(directory, text):
    path = directory / f"{UID}.json"
    directory.mkdir(mode=0o700)
    path.write_bytes(text.encode("utf-8", "surrogateescape"))
    path.chmod(0o600)
    with pytest.raises(GrantStoreError):
        GrantStore(directory).load(UID, USERNAME)


def test_interrupted_replacement_keeps_the_complete_old_record(directory):
    store = GrantStore(directory)
    first = store.write(paused_record(store))
    path = directory / f"{UID}.json"
    before = path.read_bytes()

    with mock.patch("os.replace", side_effect=OSError("interrupted")):
        with pytest.raises(GrantStoreError, match="could not be stored"):
            store.write(replace(first, intent=None))
    assert path.read_bytes() == before
    assert [entry.name for entry in directory.iterdir()] == [path.name]
    # A crash can still leave a temporary file; readers and migration ignore it.
    (directory / f".{UID}.leftover").write_text("{", encoding="utf-8")
    assert store.load(UID, USERNAME) == first
    assert store.write(replace(first, intent=None)).revision == first.revision + 1


def test_state_migration_validates_saved_time_without_rewriting_it(tmp_path):
    tmp_path.chmod(0o700)
    store = GrantStore(tmp_path / "grants")
    store.write(paused_record(store))
    path = tmp_path / "grants" / f"{UID}.json"
    (tmp_path / "grants" / f".{UID}.leftover").write_text("{", encoding="utf-8")
    before = path.read_bytes()

    assert migrate_all_state(tmp_path) == 0
    assert migrate_all_state(tmp_path) == 0
    assert path.read_bytes() == before

    future = valid_document() | {"version": 2}
    path.write_text(json.dumps(future), encoding="utf-8")
    with pytest.raises(MigrationError, match="newer than supported"):
        migrate_all_state(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == future

    path.write_text('{"version": 1, "version": 1}', encoding="utf-8")
    with pytest.raises(MigrationError, match="duplicate JSON key"):
        migrate_all_state(tmp_path)


@pytest.mark.parametrize("in_intent", (False, True))
def test_saved_limit_is_enforced_in_writes_reads_and_migration(directory, in_intent):
    store = GrantStore(directory)

    def with_balance(record, seconds):
        saved = SavedBalance(seconds, False)
        if in_intent:
            return replace(record, intent=replace(record.intent, saved=saved))
        return replace(record, saved=saved)

    before = store.write(with_balance(paused_record(store), MAX_SAVED_SECONDS))
    assert store.load(UID, USERNAME) == before
    assert migrate_all_state(directory.parent) == 0

    invalid = with_balance(before, MAX_SAVED_SECONDS + 1)
    with pytest.raises(GrantStoreError, match="saved balance"):
        store.write(invalid)
    assert store.load(UID, USERNAME) == before

    write_raw(directory, invalid.document())
    with pytest.raises(GrantStoreError, match="saved balance"):
        store.load(UID, USERNAME)
    with pytest.raises(MigrationError, match="failed current validation") as failure:
        migrate_all_state(directory.parent)
    assert isinstance(failure.value.__cause__, GrantStoreError)
    assert "saved balance" in str(failure.value.__cause__)


NOW = 1_700_000_000
MINUTE = 60


@pytest.mark.parametrize("daily, running, saved, added, beyond, usable, merged", (
    (0, 0, 0, 5 * MINUTE, 0, 0, 5 * MINUTE),
    (30 * MINUTE, 0, 0, 5 * MINUTE, 0, 30 * MINUTE, 5 * MINUTE),
    (10 * MINUTE, 20 * MINUTE, 0, 0, 10 * MINUTE, 20 * MINUTE, 10 * MINUTE),
    (20 * MINUTE, 20 * MINUTE, 7, 0, 0, 20 * MINUTE, 7),
    (30 * MINUTE, 20 * MINUTE, 20 * MINUTE, 0, 0, 30 * MINUTE, 20 * MINUTE),
    (0, 18 * MINUTE, 20 * MINUTE, 0, 18 * MINUTE, 18 * MINUTE, 38 * MINUTE),
))
def test_balance_arithmetic_conserves_daily_running_and_saved_seconds(
        daily, running, saved, added, beyond, usable, merged):
    # X is the running time beyond daily time; saving it keeps D + X == U.
    assert beyond_daily_seconds(daily, running) == beyond
    assert daily + beyond == usable == max(daily, running)
    assert merged_saved_seconds(saved, added + beyond) == merged
    # Immediate approval and redemption share max(D, A) + seconds.
    assert calculate_active_extension_seconds(daily, running, saved) == usable + saved


def test_balance_arithmetic_refuses_values_beyond_the_public_and_saved_limits():
    assert MAX_SAVED_SECONDS == MAX_TIME_GRANT_SECONDS
    assert merged_saved_seconds(MAX_SAVED_SECONDS - 1, 1) == MAX_SAVED_SECONDS
    for saved, added in ((MAX_SAVED_SECONDS, 1), (-1, 2), (1.5, 1), (True, 1), (0, UINT32_MAX + 1)):
        with pytest.raises(ValueError):
            merged_saved_seconds(saved, added)
    with pytest.raises(InvalidRequest):
        calculate_active_extension_seconds(0, UINT32_MAX, 1)
    with pytest.raises(ValueError):
        beyond_daily_seconds(-1, 0)

    assert remaining_seconds((NOW - 100, 60), NOW) == 0
    assert remaining_seconds((NOW - 60, 1200), NOW) == 1140
    assert remaining_seconds((UINT64_MAX, 0), UINT64_MAX) == 0
    for grant, now in (((UINT64_MAX + 1, 1), NOW), ((NOW, UINT32_MAX + 1), NOW),
                       ((NOW, 1), -1), ((NOW, 1.0), NOW), ((NOW + UINT32_MAX, 1), NOW)):
        with pytest.raises(ValueError):
            remaining_seconds(grant, now)


def test_running_mode_is_derived_from_the_recorded_fixed_tuple_only():
    live = (NOW - 60, 1200)
    empty = GrantRecord(UID, USERNAME)
    fixed = replace(empty, revision=3, fixed=FixedGrant(live, False),
                    saved=SavedBalance(600, True))
    paused = replace(fixed, fixed=FixedGrant(live, False, ended_by_pause=True))

    assert running_mode(fixed, live, 1140) == "fixed"
    # Pre-feature, external and rest-of-day tuples never match the record.
    assert running_mode(empty, live, 1140) == "deadline"
    assert running_mode(fixed, (NOW - 60, 1201), 1141) == "deadline"
    assert running_mode(fixed, (0, 0), 0) == "none"
    assert running_mode(fixed, live, 0) == "none"
    assert running_mode(paused, live, 1140) == "none"

    # A new grant absorbing a deadline grant with X > 0 stays deadline.
    daily_above, daily_equal, daily_below = 1141, 1140, 1139
    assert new_grant_is_fixed(empty, live, daily_above, 1140)
    assert new_grant_is_fixed(empty, live, daily_equal, 1140)
    assert not new_grant_is_fixed(empty, live, daily_below, 1140)
    assert new_grant_is_fixed(fixed, live, 0, 1140)
    assert new_grant_is_fixed(paused, live, 0, 1140)
    assert new_grant_is_fixed(empty, live, 0, 0)
