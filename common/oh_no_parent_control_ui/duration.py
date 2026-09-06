"""Compact durations shared by the parent and request interfaces."""


def format_duration(seconds):
    """Show hours when present, omit zero minutes after hours, retain seconds."""
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    parts = [f"{hours}h"] if hours else []
    if minutes or not hours:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return " ".join(parts)
