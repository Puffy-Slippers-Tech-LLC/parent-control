"""Compact durations shared by the parent and request interfaces."""

import re

from . import messages as m
from .message import JoinedMessage


def parse_duration_minutes(text):
    """Parse bounded, locale-independent m/h input without rounding.

    Return exact whole minutes or None. UI callers retain their own allowed
    range and validation feedback; raw entry text need not be a duration.
    """
    if type(text) is not str or len(text) > 16:
        return None
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]+))?([mh])", text.lower())
    if match is None:
        return None
    whole, fraction, unit = match.groups()
    scale = 10 ** len(fraction or "")
    numerator = (int(whole) * scale + int(fraction or "0")) * (60 if unit == "h" else 1)
    minutes, remainder = divmod(numerator, scale)
    return None if remainder else minutes


def format_duration(seconds):
    """Show hours when present, omit zero minutes after hours, retain seconds."""
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    parts = [m.COMPACT_HOURS % {'count': hours}] if hours else []
    if minutes or not hours:
        parts.append(m.COMPACT_MINUTES % {'count': minutes})
    if seconds:
        parts.append(m.COMPACT_SECONDS % {'count': seconds})
    return JoinedMessage(tuple(item for index, part in enumerate(parts)
                               for item in ((' ', part) if index else (part,))))
