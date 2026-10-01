"""Compact durations shared by the parent and request interfaces."""

from . import messages as m
from .message import JoinedMessage


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
