"""Deterministic generated checks for pure broker policy boundaries."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import assume, example, given, strategies as st

from oh_no_parent_control.config import UINT32_MAX
from oh_no_parent_control.core import (
    Broker,
    InvalidRequest,
    calculate_active_extension_seconds,
    seconds_until_local_midnight,
)
from oh_no_parent_control.data_migration import PREFERENCE_MIGRATIONS, migrate_document
from oh_no_parent_control.preferences import (
    PreferencesError,
    blocked_patterns,
    blocked_targets,
    default_preferences,
    validate_preferences,
)


SAFE_SUFFIXES = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=12,
)


@given(
    daily=st.integers(min_value=0, max_value=UINT32_MAX),
    grant=st.integers(min_value=0, max_value=UINT32_MAX),
    additional=st.integers(min_value=0, max_value=UINT32_MAX),
)
def test_active_extension_uses_the_later_existing_allowance(daily, grant, additional):
    if max(daily, grant) + additional > UINT32_MAX:
        with pytest.raises(InvalidRequest):
            calculate_active_extension_seconds(daily, grant, additional)
    else:
        assert calculate_active_extension_seconds(daily, grant, additional) == (
            max(daily, grant) + additional
        )


@example(daily=UINT32_MAX, grant=UINT32_MAX, additional=1)
@given(
    daily=st.integers(min_value=0, max_value=UINT32_MAX),
    grant=st.integers(min_value=0, max_value=UINT32_MAX),
    additional=st.integers(min_value=0, max_value=UINT32_MAX),
)
def test_active_extension_overflow_is_a_reproducible_invalid_request(
        daily, grant, additional):
    assume(max(daily, grant) + additional > UINT32_MAX)
    with pytest.raises(InvalidRequest):
        calculate_active_extension_seconds(daily, grant, additional)


@given(
    enabled=st.booleans(),
    limit_minutes=st.integers(min_value=0, max_value=24 * 60),
    intervals=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=1_800_000_000),
            st.integers(min_value=0, max_value=1_800_000_000),
        ),
        max_size=20,
    ),
)
def test_usage_intervals_are_clipped_and_merged_without_double_counting(
        enabled, limit_minutes, intervals):
    now = datetime(2026, 8, 30, 12, tzinfo=ZoneInfo("America/Los_Angeles"))
    now_seconds = int(now.timestamp())
    start_of_day = int(datetime(2026, 8, 30, tzinfo=now.tzinfo).timestamp())
    valid_intervals = tuple(sorted((start, end) for start, end in intervals if end >= start))
    preferences = default_preferences()
    preferences["parent_control_enabled"] = enabled
    preferences["daily_time_limit_minutes"] = limit_minutes

    broker = Broker(lambda: None, object(), object(), now=lambda: now)
    status = broker._time_status_from_usage(
        preferences, valid_intervals, 0, 0, 0, now,
    )

    clipped = sorted(
        (max(start, start_of_day), min(end, now_seconds))
        for start, end in valid_intervals
        if min(end, now_seconds) > max(start, start_of_day)
    )
    used = 0
    merged_end = None
    for start, end in clipped:
        if merged_end is None or start >= merged_end:
            used += end - start
        elif end > merged_end:
            used += end - merged_end
        merged_end = max(merged_end or 0, end)
    expected_limit = limit_minutes * 60 if enabled else 0
    assert status.daily_allowance_remaining_seconds == max(0, expected_limit - used)
    assert status.calculated_active_extension_seconds == status.daily_allowance_remaining_seconds


@given(
    date=st.dates(min_value=datetime(2025, 1, 1).date(),
                  max_value=datetime(2027, 12, 31).date()),
    hour=st.integers(min_value=0, max_value=23),
    minute=st.integers(min_value=0, max_value=59),
    second=st.integers(min_value=0, max_value=59),
    zone_name=st.sampled_from(("America/Los_Angeles", "Europe/London", "UTC")),
)
def test_local_midnight_uses_timezone_aware_epoch_arithmetic(
        date, hour, minute, second, zone_name):
    zone = ZoneInfo(zone_name)
    now = datetime(date.year, date.month, date.day, hour, minute, second, tzinfo=zone)
    tomorrow = now.date() + timedelta(days=1)
    expected = int(
        datetime.combine(tomorrow, datetime.min.time(), tzinfo=zone).timestamp()
        - now.timestamp()
    )
    assert seconds_until_local_midnight(now) == expected
    assert 0 < expected <= 26 * 60 * 60


@given(
    state=st.sampled_from(("allowed", "permanent", "conditional")),
    user_override=st.booleans(),
    use_pattern=st.booleans(),
    suffix=SAFE_SUFFIXES,
)
def test_preference_normalization_preserves_only_authorized_policy_state(
        state, user_override, use_pattern, suffix):
    target = f"/tmp/onpc-property/{suffix}.AppImage"
    value = default_preferences()
    value["apps"] = {
        f"{suffix}.desktop": {
            "state": state,
            "targets": [target],
            "patterns": [f"/tmp/onpc-property/{suffix}-*.AppImage"] if use_pattern else [],
            "user_saved_match_rule": user_override,
        },
    }

    normalized = validate_preferences(value)
    entry = normalized["apps"].get(f"{suffix}.desktop")
    if state == "allowed" and not user_override:
        assert entry is None
        assert blocked_targets(normalized, False) == ()
        assert blocked_patterns(normalized, False) == ()
    else:
        assert entry is not None
        assert entry["targets"] == [target]
        assert entry["patterns"] == (
            [f"/tmp/onpc-property/{suffix}-*.AppImage"] if use_pattern else []
        )
        assert (target in blocked_targets(normalized, False)) == (state != "allowed")
        assert (target in blocked_targets(normalized, True)) == (state == "permanent")


@given(suffix=SAFE_SUFFIXES)
def test_pattern_rejects_unsafe_basename_characters(suffix):
    value = default_preferences()
    target = f"/tmp/onpc-pattern/{suffix}.AppImage"
    value["apps"] = {
        f"{suffix}.desktop": {
            "state": "conditional",
            "targets": [target],
            "patterns": [f"/tmp/onpc-pattern/{suffix},*.AppImage"],
            "user_saved_match_rule": True,
        },
    }
    with pytest.raises(PreferencesError):
        validate_preferences(value)


@given(
    state=st.sampled_from(("allowed", "permanent", "conditional")),
    suffix=SAFE_SUFFIXES,
)
def test_preference_migrations_preserve_current_blocking_meaning(state, suffix):
    target = f"/tmp/onpc-migration/{suffix}.AppImage"
    legacy = default_preferences()
    legacy["version"] = 1
    legacy["apps"] = {
        f"{suffix}.desktop": {"state": state, "targets": [target]},
    }

    migrated, changed = migrate_document(
        legacy,
        current_version=3,
        migrations=PREFERENCE_MIGRATIONS,
        validator=validate_preferences,
    )

    assert changed
    assert migrated["version"] == 3
    assert (target in blocked_targets(migrated, False)) == (state != "allowed")
    assert blocked_patterns(migrated, False) == ()
